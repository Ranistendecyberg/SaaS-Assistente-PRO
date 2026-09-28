"""Montagem local dos links Honda; nome da classe mantido para compatibilidade."""
import base64
import re
from urllib.parse import quote, urlencode
from src.core.salesforce_utils import salesforce_15_to_18


class MedalliaBuilder:
    @staticmethod
    def identifier(sf_id, prefix):
        value = str(sf_id or '').strip()
        if not re.fullmatch(r'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?', value) or not value.startswith(prefix):
            raise ValueError('Identificador da pesquisa inválido ou incompatível com o tipo.')
        full = salesforce_15_to_18(value[:15])
        if len(value) == 18 and value != full:
            raise ValueError('Checksum do identificador da pesquisa inválido.')
        return full

    @staticmethod
    def _email(email):
        value = str(email or '').strip()
        if not re.fullmatch(r'[^@\s<>;,]+@[^@\s<>;,]+\.[^@\s<>;,]+', value):
            raise ValueError('E-mail do cliente ausente ou inválido na ficha myHonda.')
        return value

    @staticmethod
    def displacement_from_model(modelo):
        numbers = re.findall(r'\d+', str(modelo or ''))
        if len(numbers) != 1 or not 2 <= len(numbers[0]) <= 4 or not 50 <= int(numbers[0]) <= 2500:
            raise ValueError('Não foi possível identificar a cilindrada comercial no modelo myHonda.')
        return str(int(numbers[0]))

    @staticmethod
    def _encode(value):
        return base64.b64encode(value.encode('utf-8')).decode('ascii')

    @classmethod
    def build_tsi_link(cls, sf_id, email):
        params = {'e': cls._encode(cls._email(email)), 'Q1': cls._encode(cls.identifier(sf_id, 'a0O'))}
        return 'https://cloud.motos.myhonda.com.br/tsi2w?' + urlencode(params, quote_via=quote)

    @classmethod
    def build_ssi_link(cls, sf_id, modelo, *, email):
        model = ''.join(str(modelo or '').split()).upper()
        params = {'e': cls._encode(cls._email(email)), 'Q1': cls._encode(cls.identifier(sf_id, 'a0R')),
                  'Q2': cls._encode(model), 'Q3': cls.displacement_from_model(model)}
        return 'https://cloud.motos.myhonda.com.br/ssi2w?' + urlencode(params, quote_via=quote)
