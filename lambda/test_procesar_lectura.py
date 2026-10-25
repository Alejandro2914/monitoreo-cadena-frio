
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError


CARPETA_LAMBDA = Path(__file__).resolve().parent
ARCHIVO_LAMBDA = CARPETA_LAMBDA / "procesar_lectura.py"

sys.path.insert(0, str(CARPETA_LAMBDA))


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


class TestProcesarLectura(unittest.TestCase):

    def setUp(self):
        self.tabla_falsa = MagicMock()
        self.recurso_falso = MagicMock()
        self.recurso_falso.Table.return_value = self.tabla_falsa

        with patch.dict(
            os.environ,
            {"DYNAMODB_TABLE": "agrolink-lecturas"},
        ):
            with patch(
                "boto3.resource",
                return_value=self.recurso_falso,
            ):
                spec = importlib.util.spec_from_file_location(
                    "procesar_lectura_prueba",
                    ARCHIVO_LAMBDA,
                )

                self.modulo = importlib.util.module_from_spec(
                    spec
                )
                spec.loader.exec_module(self.modulo)

        self.lectura = {
            "id_acopio": "ACOPIO01",
            "id_camara": "CAMARA01",
            "id_lectura": "uuid-prueba-123",
            "marca_tiempo": "2026-10-25T01:00:00+00:00",
            "temperatura_c": 5.5,
            "humedad_pct": 75.0,
            "rango_min_c": 2.0,
            "rango_max_c": 8.0,
        }

    def test_primera_lectura(self):
        with patch.object(
            self.modulo,
            "actualizar_alerta",
            return_value="TEMPERATURA_NORMAL",
        ) as actualizar:

            resultado = self.modulo.lambda_handler(
                self.lectura,
                None,
            )

        self.assertEqual(
            resultado["resultado"],
            "almacenada",
        )

        self.assertEqual(
            resultado["evento_alerta"],
            "TEMPERATURA_NORMAL",
        )

        self.tabla_falsa.put_item.assert_called_once()
        actualizar.assert_called_once()

        argumentos = self.tabla_falsa.put_item.call_args.kwargs

        self.assertEqual(
            argumentos["Item"]["camara_id"],
            "ACOPIO01#CAMARA01",
        )

        self.assertIn(
            "attribute_not_exists",
            argumentos["ConditionExpression"],
        )

    def test_lectura_duplicada(self):
        self.tabla_falsa.put_item.side_effect = (
            error_condicional()
        )

        self.tabla_falsa.get_item.return_value = {
            "Item": {
                **self.lectura,
                "camara_id": "ACOPIO01#CAMARA01",
                "lectura_id": (
                    "2026-10-25T01:00:00+00:00#"
                    "uuid-prueba-123"
                ),
            }
        }

        with patch.object(
            self.modulo,
            "actualizar_alerta",
            return_value="LECTURA_ATRASADA",
        ) as actualizar:

            resultado = self.modulo.lambda_handler(
                self.lectura,
                None,
            )

        self.assertEqual(
            resultado["resultado"],
            "duplicada",
        )
        self.assertEqual(resultado["statusCode"], 200)

        self.tabla_falsa.get_item.assert_called_once()
        actualizar.assert_called_once()

    def test_duplicado_no_sobrescribe_temperatura(self):
        self.tabla_falsa.put_item.side_effect = (
            error_condicional()
        )

        lectura_original = {
            **self.lectura,
            "temperatura_c": 5.5,
            "camara_id": "ACOPIO01#CAMARA01",
        }

        self.tabla_falsa.get_item.return_value = {
            "Item": lectura_original
        }

        lectura_repetida = {
            **self.lectura,
            "temperatura_c": 12.0,
        }

        with patch.object(
            self.modulo,
            "actualizar_alerta",
            return_value="LECTURA_ATRASADA",
        ) as actualizar:

            resultado = self.modulo.lambda_handler(
                lectura_repetida,
                None,
            )

        self.assertEqual(
            resultado["resultado"],
            "duplicada",
        )

        lectura_evaluada = actualizar.call_args.args[1]

        self.assertEqual(
            float(lectura_evaluada["temperatura_c"]),
            5.5,
        )

    def test_alerta_sostenida(self):
        self.lectura["temperatura_c"] = 10.5
        self.lectura["marca_tiempo"] = (
            "2026-10-25T01:01:05+00:00"
        )

        estado_anterior = {
            "inicio_anomalia": "2026-10-25T01:00:00+00:00",
            "alerta_activa": False,
            "ultima_fecha_lectura": "2026-10-25T01:00:30+00:00",
            "version": 2,
        }

        with patch.object(
            self.modulo,
            "obtener_estado",
            return_value=estado_anterior,
        ), patch.object(
            self.modulo,
            "guardar_estado_y_notificacion",
            return_value=True,
        ) as transaccion:
            resultado = self.modulo.lambda_handler(
                self.lectura,
                None,
            )

        self.assertEqual(
            resultado["evento_alerta"],
            "ALERTA_ACTIVADA",
        )

        transaccion.assert_called_once()

        argumentos = transaccion.call_args.kwargs

        self.assertEqual(
            argumentos["evento"],
            "ALERTA_ACTIVADA",
        )
        self.assertTrue(
            argumentos["nuevo_estado"]["alerta_activa"]
        )


    def test_recuperacion_temperatura(self):
        self.lectura["temperatura_c"] = 5.0
        self.lectura["marca_tiempo"] = (
            "2026-10-25T01:02:00+00:00"
        )

        estado_anterior = {
            "inicio_anomalia": "2026-10-25T01:00:00+00:00",
            "alerta_activa": True,
            "ultima_fecha_lectura": "2026-10-25T01:00:30+00:00",
            "version": 3,
        }

        with patch.object(
            self.modulo,
            "obtener_estado",
            return_value=estado_anterior,
        ), patch.object(
            self.modulo,
            "guardar_estado_y_notificacion",
            return_value=True,
        ) as transaccion:
            resultado = self.modulo.lambda_handler(
                self.lectura,
                None,
            )

        self.assertEqual(
            resultado["evento_alerta"],
            "TEMPERATURA_RECUPERADA",
        )

        transaccion.assert_called_once()

        argumentos = transaccion.call_args.kwargs

        self.assertEqual(
            argumentos["evento"],
            "TEMPERATURA_RECUPERADA",
        )
        self.assertFalse(
            argumentos["nuevo_estado"]["alerta_activa"]
        )
        self.assertIsNone(
            argumentos["nuevo_estado"]["inicio_anomalia"]
        )



    def test_lectura_atrasada(self):
        estado_anterior = {
            "inicio_anomalia": None,
            "alerta_activa": False,
            "ultima_fecha_lectura": (
                "2026-10-25T02:00:00+00:00"
            ),
            "version": 4,
        }

        with patch.object(
            self.modulo,
            "obtener_estado",
            return_value=estado_anterior,
        ), patch.object(
            self.modulo,
            "guardar_estado",
        ) as guardar:

            resultado = self.modulo.lambda_handler(
                self.lectura,
                None,
            )

        self.assertEqual(
            resultado["evento_alerta"],
            "LECTURA_ATRASADA",
        )
        guardar.assert_not_called()

    def test_reintenta_conflicto_concurrencia(self):
        with patch.object(
            self.modulo,
            "obtener_estado",
            return_value=None,
        ) as obtener, patch.object(
            self.modulo,
            "guardar_estado",
            side_effect=[False, True],
        ) as guardar:

            resultado = self.modulo.lambda_handler(
                self.lectura,
                None,
            )

        self.assertEqual(
            resultado["evento_alerta"],
            "TEMPERATURA_NORMAL",
        )

        self.assertEqual(obtener.call_count, 2)
        self.assertEqual(guardar.call_count, 2)

    def test_error_si_no_puede_actualizar_estado(self):
        with patch.object(
            self.modulo,
            "obtener_estado",
            return_value=None,
        ), patch.object(
            self.modulo,
            "guardar_estado",
            return_value=False,
        ) as guardar:

            with self.assertRaises(RuntimeError):
                self.modulo.lambda_handler(
                    self.lectura,
                    None,
                )

        self.assertEqual(guardar.call_count, 5)


if __name__ == "__main__":
    unittest.main()
