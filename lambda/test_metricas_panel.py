
import os
import unittest
from unittest.mock import MagicMock, patch

from boto3.dynamodb.conditions import Key

with patch.dict(
    os.environ,
    {"DYNAMODB_TABLE": "agrolink-lecturas"},
):
    import metricas_panel


class TestMetricasPanel(unittest.TestCase):

    def setUp(self):
        self.tabla = MagicMock()
        self.cloudwatch = MagicMock()

    def test_ocho_camaras_configuradas(self):
        self.assertEqual(
            len(metricas_panel.CAMARAS),
            8,
        )
        self.assertEqual(
            metricas_panel.CAMARAS[0],
            "ACOPIO01#CAMARA01",
        )
        self.assertEqual(
            metricas_panel.CAMARAS[-1],
            "ACOPIO08#CAMARA01",
        )

    def test_consulta_ultima_lectura(self):
        lectura = {
            "lectura_id": "2026-10-26T02:17:00Z#abc",
            "temperatura_c": 5.5,
        }

        self.tabla.query.return_value = {
            "Items": [lectura],
        }

        resultado = metricas_panel.obtener_ultima_lectura(
            self.tabla,
            "ACOPIO01#CAMARA01",
        )

        self.assertEqual(resultado, lectura)

        argumentos = self.tabla.query.call_args.kwargs

        self.assertFalse(
            argumentos["ScanIndexForward"]
        )
        self.assertEqual(
            argumentos["Limit"],
            1,
        )
        self.assertTrue(
            argumentos["ConsistentRead"]
        )
        self.assertIn(
            "KeyConditionExpression",
            argumentos,
        )

    def test_sin_lecturas_no_publica_metrica(self):
        with patch.object(
            metricas_panel,
            "CAMARAS",
            ["ACOPIO01#CAMARA01"],
        ):
            self.tabla.query.return_value = {
                "Items": [],
            }

            resultado = (
                metricas_panel.publicar_temperaturas(
                    self.tabla,
                    self.cloudwatch,
                )
            )

        self.assertEqual(
            resultado["ACOPIO01#CAMARA01"]["estado"],
            "SIN_LECTURAS",
        )
        self.cloudwatch.put_metric_data.assert_not_called()

    def test_publica_temperatura_cloudwatch(self):
        lectura = {
            "lectura_id": "2026-10-26T02:17:00Z#abc",
            "marca_tiempo": "2026-10-26T02:17:00Z",
            "temperatura_c": 6.5,
        }

        self.tabla.query.return_value = {
            "Items": [lectura],
        }

        with patch.object(
            metricas_panel,
            "CAMARAS",
            ["ACOPIO01#CAMARA01"],
        ):
            resultado = (
                metricas_panel.publicar_temperaturas(
                    self.tabla,
                    self.cloudwatch,
                )
            )

        self.assertEqual(
            resultado["ACOPIO01#CAMARA01"]["estado"],
            "PUBLICADA",
        )

        argumentos = (
            self.cloudwatch.put_metric_data.call_args.kwargs
        )

        self.assertEqual(
            argumentos["Namespace"],
            "AgroLink/CadenaFrio",
        )
        self.assertEqual(
            argumentos["MetricData"][0]["MetricName"],
            "UltimaTemperatura",
        )
        self.assertEqual(
            argumentos["MetricData"][0]["Value"],
            6.5,
        )
        self.assertEqual(
            argumentos["MetricData"][0]["Dimensions"][0]["Value"],
            "ACOPIO01#CAMARA01",
        )


if __name__ == "__main__":
    unittest.main()
