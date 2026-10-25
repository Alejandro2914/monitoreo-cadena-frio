
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from estado_alertas import (
    CLAVE_ESTADO,
    obtener_estado,
    guardar_estado,
)


def error_condicional():
    return ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "Conditional request failed",
            }
        },
        "PutItem",
    )


class TestEstadoAlertas(unittest.TestCase):

    def setUp(self):
        self.tabla = MagicMock()
        self.camara_id = "ACOPIO03#CAMARA01"

        self.nuevo_estado = {
            "inicio_anomalia": "2026-10-25T01:00:00+00:00",
            "alerta_activa": False,
            "ultima_fecha_lectura": "2026-10-25T01:00:00+00:00",
        }

    def test_estado_inexistente(self):
        self.tabla.get_item.return_value = {}

        resultado = obtener_estado(self.camara_id, self.tabla)

        self.assertIsNone(resultado)

    def test_consultar_estado_existente(self):
        self.tabla.get_item.return_value = {
            "Item": {
                "inicio_anomalia": "2026-10-25T01:00:00+00:00",
                "alerta_activa": True,
                "ultima_fecha_lectura": "2026-10-25T01:01:00+00:00",
                "version": 3,
            }
        }

        resultado = obtener_estado(self.camara_id, self.tabla)

        self.assertTrue(resultado["alerta_activa"])
        self.assertEqual(resultado["version"], 3)

    def test_crear_estado(self):
        resultado = guardar_estado(
            self.camara_id,
            self.nuevo_estado,
            estado_anterior=None,
            tabla=self.tabla,
        )

        self.assertTrue(resultado)
        self.tabla.put_item.assert_called_once()

        argumentos = self.tabla.put_item.call_args.kwargs

        self.assertEqual(
            argumentos["Item"]["lectura_id"],
            CLAVE_ESTADO,
        )
        self.assertEqual(
            argumentos["Item"]["version"],
            1,
        )

    def test_estado_duplicado_por_concurrencia(self):
        self.tabla.put_item.side_effect = error_condicional()

        resultado = guardar_estado(
            self.camara_id,
            self.nuevo_estado,
            estado_anterior=None,
            tabla=self.tabla,
        )

        self.assertFalse(resultado)

    def test_actualizar_estado(self):
        estado_anterior = {
            "version": 2,
        }

        resultado = guardar_estado(
            self.camara_id,
            self.nuevo_estado,
            estado_anterior=estado_anterior,
            tabla=self.tabla,
        )

        self.assertTrue(resultado)
        self.tabla.update_item.assert_called_once()

        argumentos = self.tabla.update_item.call_args.kwargs

        self.assertEqual(
            argumentos["ExpressionAttributeValues"][":nueva_version"],
            3,
        )

    def test_conflicto_de_actualizacion(self):
        self.tabla.update_item.side_effect = error_condicional()

        resultado = guardar_estado(
            self.camara_id,
            self.nuevo_estado,
            estado_anterior={"version": 2},
            tabla=self.tabla,
        )

        self.assertFalse(resultado)


if __name__ == "__main__":
    unittest.main()
