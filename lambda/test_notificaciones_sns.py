
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

CARPETA_LAMBDA = Path(__file__).resolve().parent
sys.path.insert(0, str(CARPETA_LAMBDA))

from notificaciones_sns import publicar_notificacion


class TestNotificacionesSNS(unittest.TestCase):

    def setUp(self):
        self.camara_id = "ACOPIO08#CAMARA01"

        self.lectura = {
            "id_acopio": "ACOPIO08",
            "id_camara": "CAMARA01",
            "temperatura_c": 10.5,
            "marca_tiempo": "2026-10-25T01:19:05+00:00",
        }

    @patch("notificaciones_sns.boto3.client")
    def test_publicar_alerta_activada(self, cliente_falso):
        sns = MagicMock()
        sns.publish.return_value = {
            "MessageId": "mensaje-alerta-001"
        }
        cliente_falso.return_value = sns

        with patch.dict(
            os.environ,
            {
                "SNS_TOPIC_ARN": (
                    "arn:aws:sns:us-east-2:619071328452:"
                    "agrolink-alertas-cadena-frio"
                )
            },
        ):
            resultado = publicar_notificacion(
                self.camara_id,
                self.lectura,
                "ALERTA_ACTIVADA",
            )

        self.assertTrue(resultado["publicada"])
        self.assertEqual(
            resultado["message_id"],
            "mensaje-alerta-001",
        )
        sns.publish.assert_called_once()

    @patch("notificaciones_sns.boto3.client")
    def test_publicar_temperatura_recuperada(self, cliente_falso):
        sns = MagicMock()
        sns.publish.return_value = {
            "MessageId": "mensaje-recuperacion-001"
        }
        cliente_falso.return_value = sns

        with patch.dict(
            os.environ,
            {
                "SNS_TOPIC_ARN": (
                    "arn:aws:sns:us-east-2:619071328452:"
                    "agrolink-alertas-cadena-frio"
                )
            },
        ):
            resultado = publicar_notificacion(
                self.camara_id,
                self.lectura,
                "TEMPERATURA_RECUPERADA",
            )

        self.assertTrue(resultado["publicada"])
        sns.publish.assert_called_once()

    @patch("notificaciones_sns.boto3.client")
    def test_no_publicar_evento_normal(self, cliente_falso):
        resultado = publicar_notificacion(
            self.camara_id,
            self.lectura,
            "TEMPERATURA_NORMAL",
        )

        self.assertFalse(resultado["publicada"])
        cliente_falso.assert_not_called()

    @patch("notificaciones_sns.boto3.client")
    def test_no_publicar_alerta_continua(self, cliente_falso):
        resultado = publicar_notificacion(
            self.camara_id,
            self.lectura,
            "ALERTA_CONTINUA",
        )

        self.assertFalse(resultado["publicada"])
        cliente_falso.assert_not_called()


if __name__ == "__main__":
    unittest.main()
