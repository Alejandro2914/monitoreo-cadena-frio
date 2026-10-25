
import unittest
from unittest.mock import MagicMock, patch

from despachar_notificaciones import procesar_registro


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
            "Item": {
                "evento": "ALERTA_ACTIVADA",
                "estado_envio": "PENDIENTE",
                "id_acopio": "ACOPIO01",
                "id_camara": "CAMARA01",
                "temperatura_c": 11.5,
                "marca_tiempo": "2026-10-25T10:00:00Z",
            }
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


if __name__ == "__main__":
    unittest.main()
