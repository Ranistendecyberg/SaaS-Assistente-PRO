import unittest

from src.core.v2_business_rules import is_valid_cpf, is_valid_cnpj, is_valid_document


class TaxDocumentTests(unittest.TestCase):
    def test_valid_documents(self):
        self.assertTrue(is_valid_cpf("529.982.247-25"))
        self.assertTrue(is_valid_cnpj("11.222.333/0001-81"))
        for value in ("52998224725", "11222333000181"):
            self.assertTrue(is_valid_document(value))

    def test_invalid_documents(self):
        for value in (None, "", "11111111111", "00000000000000", "52998224724", "11222333000182", "123", "５２９９８２２４７２５"):
            with self.subTest(value=value):
                self.assertFalse(is_valid_document(value))

    def test_types_not_interchangeable(self):
        self.assertFalse(is_valid_cpf("11222333000181"))
        self.assertFalse(is_valid_cnpj("52998224725"))
