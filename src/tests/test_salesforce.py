import unittest
from src.core.salesforce_utils import salesforce_15_to_18

class TestSalesforceUtils(unittest.TestCase):
    def test_conversion_valid(self):
        # Baseado no exemplo da documentação
        original = "a0OVP000007sCQo"
        esperado = "a0OVP000007sCQo2AM"
        self.assertEqual(salesforce_15_to_18(original), esperado)
        
    def test_conversion_ignore_if_already_18(self):
        # Se passar 18 ou algo diferente, retorna o mesmo
        ja_convertido = "a0OVP000007sCQo2AM"
        self.assertEqual(salesforce_15_to_18(ja_convertido), ja_convertido)

if __name__ == '__main__':
    unittest.main()
