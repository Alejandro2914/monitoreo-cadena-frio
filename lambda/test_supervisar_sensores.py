
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from supervisar_sensores import (
    CAMARAS,
    actualizar_estado,
    determinar_estado,
    enviar_notificacion,
    supervisar_camara,
)


class TestSupervisarSensores(unittest.TestCase):

    def setUp(self):
        self.tabla = MagicMock()
        self.sns = MagicMock()
        self.camara_id = "ACOPIO01#CAMARA01"
        self.ahora = 1000

    def crear_registro(
        self,
        ultima_recepcion=950,
        estado="CONECTADO",
    ):
        registro = {
            "camara_id": self.camara_id,
            "lectura_id": "ESTADO#CONEXION",
            "ultima_recepcion_epoch": ultima_recepcion,
            "ultima_recepcion_utc": "2026-10-25T20:00:00+00:00",
        }

        if estado is not None:
            registro["estado_supervision"] = estado

        return registro

    def test_ocho_camaras_configuradas(self):
        self.assertEqual(len(CAMARAS), 8)
        self.assertEqual(CAMARAS[0], "ACOPIO01#CAMARA01")
        self.assertEqual(CAMARAS[-1], "ACOPIO08#CAMARA01")

    def test_sensor_activo(self):
        registro = self.crear_registro(
            ultima_recepcion=950
        )

        estado, segundos = determinar_estado(
            registro,
            self.ahora,
        )

        self.assertEqual(estado, "CONECTADO")
        self.assertEqual(segundos, 50)

    def test_sensor_desconectado(self):
        registro = self.crear_registro(
            ultima_recepcion=800
        )

        estado, segundos = determinar_estado(
            registro,
            self.ahora,
        )

        self.assertEqual(estado, "DESCONECTADO")
        self.assertEqual(segundos, 200)

    def test_umbral_exacto_no_desconecta(self):
        registro = self.crear_registro(
            ultima_recepcion=880
        )

        estado, segundos = determinar_estado(
            registro,
            self.ahora,
        )

        self.assertEqual(estado, "CONECTADO")
        self.assertEqual(segundos, 120)

    @patch("supervisar_sensores.obtener_estado")
    def test_no_supervisa_sin_registro(
        self,
        mock_obtener,
    ):
        mock_obtener.return_value = None

        resultado = supervisar_camara(
            self.tabla,
            self.sns,
            self.camara_id,
            self.ahora,
        )

        self.assertEqual(resultado, "SIN_DATOS")
        self.sns.publish.assert_not_called()

    @patch("supervisar_sensores.obtener_estado")
    def test_no_repite_alerta_desconectado(
        self,
        mock_obtener,
    ):
        mock_obtener.return_value = self.crear_registro(
            ultima_recepcion=800,
            estado="DESCONECTADO",
        )

        resultado = supervisar_camara(
            self.tabla,
            self.sns,
            self.camara_id,
            self.ahora,
        )

        self.assertEqual(resultado, "DESCONECTADO")
        self.tabla.update_item.assert_not_called()
        self.sns.publish.assert_not_called()

    @patch("supervisar_sensores.obtener_estado")
    def test_detecta_transicion_desconexion(
        self,
        mock_obtener,
    ):
        mock_obtener.side_effect = [
            self.crear_registro(
                ultima_recepcion=800,
                estado="CONECTADO",
            ),
            self.crear_registro(
                ultima_recepcion=800,
                estado="DESCONECTADO",
            ),
        ]

        resultado = supervisar_camara(
            self.tabla,
            self.sns,
            self.camara_id,
            self.ahora,
        )

        self.assertEqual(resultado, "DESCONECTADO")

        self.assertEqual(
            self.tabla.update_item.call_count,
            1,
        )

        argumentos = self.tabla.update_item.call_args.kwargs

        self.assertEqual(
            argumentos["ExpressionAttributeValues"][":nuevo"],
            "DESCONECTADO",
        )

    @patch("supervisar_sensores.obtener_estado")
    def test_detecta_transicion_reconexion(
        self,
        mock_obtener,
    ):
        mock_obtener.side_effect = [
            self.crear_registro(
                ultima_recepcion=950,
                estado="DESCONECTADO",
            ),
            self.crear_registro(
                ultima_recepcion=950,
                estado="CONECTADO",
            ),
        ]

        resultado = supervisar_camara(
            self.tabla,
            self.sns,
            self.camara_id,
            self.ahora,
        )

        self.assertEqual(resultado, "CONECTADO")

        argumentos = self.tabla.update_item.call_args.kwargs

        self.assertEqual(
            argumentos["ExpressionAttributeValues"][":nuevo"],
            "CONECTADO",
        )

    def test_primera_supervision_no_crea_alerta(self):
        registro = self.crear_registro(
            ultima_recepcion=800,
            estado=None,
        )

        resultado = actualizar_estado(
            self.tabla,
            self.camara_id,
            registro,
            "DESCONECTADO",
            self.ahora,
        )

        self.assertTrue(resultado)

        argumentos = self.tabla.update_item.call_args.kwargs

        self.assertNotIn(
            ":evento",
            argumentos["ExpressionAttributeValues"],
        )

    def test_publica_notificacion_pendiente(self):
        registro = self.crear_registro(
            ultima_recepcion=800,
            estado="DESCONECTADO",
        )

        registro["notificacion_pendiente"] = (
            "SENSOR_DESCONECTADO"
        )

        self.sns.publish.return_value = {
            "MessageId": "sns-sensor-001"
        }

        with patch.dict(
            "os.environ",
            {
                "SNS_TOPIC_ARN": (
                    "arn:aws:sns:us-east-2:"
                    "619071328452:"
                    "agrolink-alertas-cadena-frio"
                )
            },
        ):
            resultado = enviar_notificacion(
                self.tabla,
                self.sns,
                self.camara_id,
                registro,
                self.ahora,
            )

        self.assertTrue(resultado)
        self.sns.publish.assert_called_once()
        self.tabla.update_item.assert_called_once()

    def test_fallo_sns_conserva_pendiente(self):
        registro = self.crear_registro(
            ultima_recepcion=800,
            estado="DESCONECTADO",
        )

        registro["notificacion_pendiente"] = (
            "SENSOR_DESCONECTADO"
        )

        self.sns.publish.side_effect = RuntimeError(
            "SNS no disponible"
        )

        with patch.dict(
            "os.environ",
            {"SNS_TOPIC_ARN": "arn:aws:sns:us-east-2:123:test"},
        ):
            with self.assertRaises(RuntimeError):
                enviar_notificacion(
                    self.tabla,
                    self.sns,
                    self.camara_id,
                    registro,
                    self.ahora,
                )

        self.tabla.update_item.assert_not_called()

    def test_conflicto_concurrencia(self):
        registro = self.crear_registro(
            ultima_recepcion=800,
            estado="CONECTADO",
        )

        self.tabla.update_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Conditional request failed",
                }
            },
            "UpdateItem",
        )

        resultado = actualizar_estado(
            self.tabla,
            self.camara_id,
            registro,
            "DESCONECTADO",
            self.ahora,
        )

        self.assertFalse(resultado)


if __name__ == "__main__":
    unittest.main()
