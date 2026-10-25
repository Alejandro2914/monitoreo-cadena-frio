
import unittest
from unittest.mock import ANY, MagicMock, patch

from botocore.exceptions import ClientError

from despachar_notificaciones import (
    liberar_notificacion,
    marcar_enviada,
    procesar_registro,
    reclamar_notificacion,
)


class TestDespacharNotificaciones(unittest.TestCase):

    def crear_registro(
        self,
        event_name="INSERT",
        lectura_id="NOTIFICACION#001#ALERTA_ACTIVADA",
    ):
        return {
            "eventName": event_name,
            "dynamodb": {
                "Keys": {
                    "camara_id": {
                        "S": "ACOPIO01#CAMARA01"
                    },
                    "lectura_id": {
                        "S": lectura_id
                    },
                }
            },
        }

    def crear_notificacion(self):
        return {
            "evento": "ALERTA_ACTIVADA",
            "estado_envio": "PENDIENTE",
            "id_acopio": "ACOPIO01",
            "id_camara": "CAMARA01",
            "temperatura_c": 11.5,
            "marca_tiempo": "2026-10-25T10:00:00Z",
        }

    @patch("despachar_notificaciones.obtener_tabla")
    def test_ignora_lecturas_normales(self, mock_tabla):
        registro = self.crear_registro(
            lectura_id="2026-10-25T10:00:00Z#001"
        )

        procesar_registro(registro)

        mock_tabla.assert_not_called()

    @patch("despachar_notificaciones.obtener_tabla")
    def test_ignora_eventos_modify(self, mock_tabla):
        registro = self.crear_registro(
            event_name="MODIFY"
        )

        procesar_registro(registro)

        mock_tabla.assert_not_called()

    @patch("despachar_notificaciones.marcar_enviada")
    @patch("despachar_notificaciones.publicar_notificacion")
    @patch("despachar_notificaciones.reclamar_notificacion")
    @patch("despachar_notificaciones.obtener_tabla")
    def test_publica_alerta_pendiente(
        self,
        mock_obtener_tabla,
        mock_reclamar,
        mock_publicar,
        mock_marcar,
    ):
        tabla = MagicMock()
        mock_obtener_tabla.return_value = tabla

        tabla.get_item.return_value = {
            "Item": self.crear_notificacion()
        }

        mock_reclamar.return_value = True
        mock_publicar.return_value = {
            "publicada": True,
            "message_id": "sns-message-001",
        }

        procesar_registro(self.crear_registro())

        mock_publicar.assert_called_once()

        mock_marcar.assert_called_once_with(
            tabla,
            "ACOPIO01#CAMARA01",
            "NOTIFICACION#001#ALERTA_ACTIVADA",
            "sns-message-001",
            ANY,
        )

    @patch("despachar_notificaciones.publicar_notificacion")
    @patch("despachar_notificaciones.reclamar_notificacion")
    @patch("despachar_notificaciones.obtener_tabla")
    def test_no_reenvia_notificacion_enviada(
        self,
        mock_obtener_tabla,
        mock_reclamar,
        mock_publicar,
    ):
        tabla = MagicMock()
        mock_obtener_tabla.return_value = tabla

        tabla.get_item.return_value = {
            "Item": {
                "evento": "ALERTA_ACTIVADA",
                "estado_envio": "ENVIADA",
            }
        }

        mock_reclamar.return_value = False

        procesar_registro(self.crear_registro())

        mock_publicar.assert_not_called()

    @patch("despachar_notificaciones.liberar_notificacion")
    @patch("despachar_notificaciones.marcar_enviada")
    @patch("despachar_notificaciones.publicar_notificacion")
    @patch("despachar_notificaciones.reclamar_notificacion")
    @patch("despachar_notificaciones.obtener_tabla")
    def test_no_libera_si_sns_publico_pero_dynamodb_fallo(
        self,
        mock_obtener_tabla,
        mock_reclamar,
        mock_publicar,
        mock_marcar,
        mock_liberar,
    ):
        tabla = MagicMock()
        mock_obtener_tabla.return_value = tabla

        tabla.get_item.return_value = {
            "Item": self.crear_notificacion()
        }

        mock_reclamar.return_value = True
        mock_publicar.return_value = {
            "publicada": True,
            "message_id": "sns-message-001",
        }

        mock_marcar.side_effect = RuntimeError(
            "Error al actualizar DynamoDB"
        )

        with self.assertRaises(RuntimeError):
            procesar_registro(self.crear_registro())

        mock_publicar.assert_called_once()
        mock_liberar.assert_not_called()

    @patch("despachar_notificaciones.liberar_notificacion")
    @patch("despachar_notificaciones.publicar_notificacion")
    @patch("despachar_notificaciones.reclamar_notificacion")
    @patch("despachar_notificaciones.obtener_tabla")
    def test_libera_si_sns_falla(
        self,
        mock_obtener_tabla,
        mock_reclamar,
        mock_publicar,
        mock_liberar,
    ):
        tabla = MagicMock()
        mock_obtener_tabla.return_value = tabla

        tabla.get_item.return_value = {
            "Item": self.crear_notificacion()
        }

        mock_reclamar.return_value = True

        mock_publicar.side_effect = RuntimeError(
            "SNS no disponible"
        )

        with self.assertRaises(RuntimeError):
            procesar_registro(self.crear_registro())

        mock_liberar.assert_called_once_with(
            tabla,
            "ACOPIO01#CAMARA01",
            "NOTIFICACION#001#ALERTA_ACTIVADA",
            ANY,
        )

    def test_reclamar_registra_token_unico(self):
        tabla = MagicMock()

        resultado = reclamar_notificacion(
            tabla,
            "ACOPIO01#CAMARA01",
            "NOTIFICACION#001#ALERTA_ACTIVADA",
            "token-ejecucion-123",
        )

        self.assertTrue(resultado)

        argumentos = tabla.update_item.call_args.kwargs

        self.assertEqual(
            argumentos["ExpressionAttributeValues"][":token"],
            "token-ejecucion-123",
        )

        self.assertIn(
            "token_bloqueo = :token",
            argumentos["UpdateExpression"],
        )

    def test_marcar_enviada_exige_token_correcto(self):
        tabla = MagicMock()

        marcar_enviada(
            tabla,
            "ACOPIO01#CAMARA01",
            "NOTIFICACION#001#ALERTA_ACTIVADA",
            "sns-message-001",
            "token-ejecucion-123",
        )

        argumentos = tabla.update_item.call_args.kwargs

        self.assertIn(
            "token_bloqueo = :token",
            argumentos["ConditionExpression"],
        )

        self.assertEqual(
            argumentos["ExpressionAttributeValues"][":token"],
            "token-ejecucion-123",
        )

    def test_liberar_exige_token_correcto(self):
        tabla = MagicMock()

        liberar_notificacion(
            tabla,
            "ACOPIO01#CAMARA01",
            "NOTIFICACION#001#ALERTA_ACTIVADA",
            "token-ejecucion-123",
        )

        argumentos = tabla.update_item.call_args.kwargs

        self.assertIn(
            "token_bloqueo = :token",
            argumentos["ConditionExpression"],
        )

        self.assertEqual(
            argumentos["ExpressionAttributeValues"][":token"],
            "token-ejecucion-123",
        )

    def test_no_reclama_si_existe_otro_bloqueo(self):
        tabla = MagicMock()

        tabla.update_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "Conditional request failed",
                }
            },
            "UpdateItem",
        )

        resultado = reclamar_notificacion(
            tabla,
            "ACOPIO01#CAMARA01",
            "NOTIFICACION#001#ALERTA_ACTIVADA",
            "token-nuevo",
        )

        self.assertFalse(resultado)


if __name__ == "__main__":
    unittest.main()
