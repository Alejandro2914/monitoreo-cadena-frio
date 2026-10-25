
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent),
)

from eventos_notificacion import (
    crear_identificador_evento,
    registrar_evento,
)


class TestEventosNotificacion(unittest.TestCase):

    def setUp(self):
        self.tabla = MagicMock()
        self.camara_id = "ACOPIO08#CAMARA01"

        self.lectura = {
            "camara_id": self.camara_id,
            "lectura_id": (
                "2026-10-25T01:19:05+00:00#uuid-123"
            ),
            "id_acopio": "ACOPIO08",
            "id_camara": "CAMARA01",
            "temperatura_c": 11.2,
            "marca_tiempo": "2026-10-25T01:19:05+00:00",
        }

    def test_identificador_unico(self):
        identificador = crear_identificador_evento(
            self.lectura["lectura_id"],
            "ALERTA_ACTIVADA",
        )

        self.assertEqual(
            identificador,
            (
                "NOTIFICACION#"
                "2026-10-25T01:19:05+00:00#uuid-123"
                "#ALERTA_ACTIVADA"
            ),
        )

    def test_registrar_alerta_activada(self):
        identificador = registrar_evento(
            self.tabla,
            self.camara_id,
            self.lectura,
            "ALERTA_ACTIVADA",
        )

        self.assertIsNotNone(identificador)
        self.tabla.put_item.assert_called_once()

        item = self.tabla.put_item.call_args.kwargs["Item"]

        self.assertEqual(item["estado_envio"], "PENDIENTE")
        self.assertEqual(item["evento"], "ALERTA_ACTIVADA")
        self.assertEqual(item["tipo_registro"], "NOTIFICACION")

    def test_registrar_recuperacion(self):
        identificador = registrar_evento(
            self.tabla,
            self.camara_id,
            self.lectura,
            "TEMPERATURA_RECUPERADA",
        )

        self.assertIsNotNone(identificador)
        self.tabla.put_item.assert_called_once()

    def test_no_registrar_temperatura_normal(self):
        resultado = registrar_evento(
            self.tabla,
            self.camara_id,
            self.lectura,
            "TEMPERATURA_NORMAL",
        )

        self.assertIsNone(resultado)
        self.tabla.put_item.assert_not_called()

    def test_no_registrar_alerta_continua(self):
        resultado = registrar_evento(
            self.tabla,
            self.camara_id,
            self.lectura,
            "ALERTA_CONTINUA",
        )

        self.assertIsNone(resultado)
        self.tabla.put_item.assert_not_called()

    def test_registro_duplicado(self):
        self.tabla.put_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "El evento ya existe",
                }
            },
            "PutItem",
        )

        identificador = registrar_evento(
            self.tabla,
            self.camara_id,
            self.lectura,
            "ALERTA_ACTIVADA",
        )

        self.assertIsNotNone(identificador)
        self.tabla.put_item.assert_called_once()


if __name__ == "__main__":
    unittest.main()
