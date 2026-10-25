
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from transaccion_alertas import guardar_estado_y_notificacion


class TestTransaccionAlertas(unittest.TestCase):

    def setUp(self):
        self.cliente = MagicMock()
        self.camara_id = "ACOPIO08#CAMARA01"

        self.lectura = {
            "camara_id": self.camara_id,
            "lectura_id": "2026-10-25T01:19:05+00:00#uuid-123",
            "id_acopio": "ACOPIO08",
            "id_camara": "CAMARA01",
            "temperatura_c": 11.2,
            "marca_tiempo": "2026-10-25T01:19:05+00:00",
        }

        self.estado_anterior = {
            "inicio_anomalia": "2026-10-25T01:18:00+00:00",
            "alerta_activa": False,
            "ultima_fecha_lectura": "2026-10-25T01:18:00+00:00",
            "version": 2,
        }

        self.nuevo_estado = {
            "inicio_anomalia": "2026-10-25T01:18:00+00:00",
            "alerta_activa": True,
            "ultima_fecha_lectura": "2026-10-25T01:19:05+00:00",
        }

    def ejecutar(self, estado_anterior=None):
        return guardar_estado_y_notificacion(
            camara_id=self.camara_id,
            lectura=self.lectura,
            evento="ALERTA_ACTIVADA",
            nuevo_estado=self.nuevo_estado,
            estado_anterior=estado_anterior,
            cliente=self.cliente,
            nombre_tabla="agrolink-lecturas",
        )

    def test_transaccion_exitosa(self):
        resultado = self.ejecutar(self.estado_anterior)

        self.assertTrue(resultado)
        self.cliente.transact_write_items.assert_called_once()

        operaciones = (
            self.cliente.transact_write_items.call_args.kwargs[
                "TransactItems"
            ]
        )

        self.assertEqual(len(operaciones), 2)
        self.assertIn("Update", operaciones[0])
        self.assertIn("Put", operaciones[1])

    def test_evento_pendiente(self):
        self.ejecutar(self.estado_anterior)

        operaciones = (
            self.cliente.transact_write_items.call_args.kwargs[
                "TransactItems"
            ]
        )

        item = operaciones[1]["Put"]["Item"]

        self.assertEqual(
            item["estado_envio"]["S"],
            "PENDIENTE",
        )
        self.assertEqual(
            item["evento"]["S"],
            "ALERTA_ACTIVADA",
        )

    def test_conflicto_condicional(self):
        self.cliente.transact_write_items.side_effect = ClientError(
            {
                "Error": {
                    "Code": "TransactionCanceledException",
                    "Message": "Transaction cancelled",
                },
                "CancellationReasons": [
                    {"Code": "ConditionalCheckFailed"},
                    {"Code": "None"},
                ],
            },
            "TransactWriteItems",
        )

        resultado = self.ejecutar(self.estado_anterior)

        self.assertFalse(resultado)

    def test_error_aws_se_propaga(self):
        self.cliente.transact_write_items.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Access denied",
                }
            },
            "TransactWriteItems",
        )

        with self.assertRaises(ClientError):
            self.ejecutar(self.estado_anterior)

    def test_rechazar_evento_no_notificable(self):
        with self.assertRaises(ValueError):
            guardar_estado_y_notificacion(
                camara_id=self.camara_id,
                lectura=self.lectura,
                evento="TEMPERATURA_NORMAL",
                nuevo_estado=self.nuevo_estado,
                estado_anterior=self.estado_anterior,
                cliente=self.cliente,
                nombre_tabla="agrolink-lecturas",
            )

        self.cliente.transact_write_items.assert_not_called()

    def test_crear_estado_y_evento(self):
        resultado = self.ejecutar(estado_anterior=None)

        self.assertTrue(resultado)

        operaciones = (
            self.cliente.transact_write_items.call_args.kwargs[
                "TransactItems"
            ]
        )

        self.assertIn("Put", operaciones[0])
        self.assertIn("Put", operaciones[1])

    def test_version_incrementada(self):
        self.ejecutar(self.estado_anterior)

        operaciones = (
            self.cliente.transact_write_items.call_args.kwargs[
                "TransactItems"
            ]
        )

        valores = operaciones[0]["Update"][
            "ExpressionAttributeValues"
        ]

        self.assertEqual(
            valores[":version_actual"]["N"],
            "2",
        )
        self.assertEqual(
            valores[":version_nueva"]["N"],
            "3",
        )


if __name__ == "__main__":
    unittest.main()
