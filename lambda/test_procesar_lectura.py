
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError


ARCHIVO_LAMBDA = Path(__file__).with_name("procesar_lectura.py")


class TestDeduplicacion(unittest.TestCase):

    def setUp(self):
        self.tabla_falsa = MagicMock()
        self.recurso_falso = MagicMock()
        self.recurso_falso.Table.return_value = self.tabla_falsa

        with patch.dict(os.environ, {"DYNAMODB_TABLE": "agrolink-lecturas"}):
            with patch("boto3.resource", return_value=self.recurso_falso):
                spec = importlib.util.spec_from_file_location(
                    "procesar_lectura_prueba",
                    ARCHIVO_LAMBDA
                )
                self.modulo = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self.modulo)

        self.lectura = {
            "id_acopio": "ACOPIO01",
            "id_camara": "CAMARA01",
            "id_lectura": "uuid-prueba-123",
            "marca_tiempo": "2026-10-23T23:00:00+00:00",
            "temperatura_c": 5.5,
            "humedad_pct": 75.0
        }

    def test_primera_lectura(self):
        resultado = self.modulo.lambda_handler(self.lectura, None)

        self.assertEqual(resultado["resultado"], "almacenada")
        self.tabla_falsa.put_item.assert_called_once()

        argumentos = self.tabla_falsa.put_item.call_args.kwargs
        self.assertEqual(
            argumentos["Item"]["camara_id"],
            "ACOPIO01#CAMARA01"
        )
        self.assertIn("attribute_not_exists", argumentos["ConditionExpression"])

    def test_lectura_duplicada(self):
        self.tabla_falsa.put_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "La lectura ya existe"
                }
            },
            "PutItem"
        )

        resultado = self.modulo.lambda_handler(self.lectura, None)

        self.assertEqual(resultado["resultado"], "duplicada")
        self.assertEqual(resultado["statusCode"], 200)


if __name__ == "__main__":
    unittest.main()
