def salesforce_15_to_18(sf_id: str) -> str:
    """
    Converte um ID do Salesforce de 15 caracteres para 18 caracteres API-Safe.
    Utiliza o algoritmo de Checksum Bitwise.
    """
    if len(sf_id) != 15:
        return sf_id
        
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
    suffix = ""
    for i in range(3):
        chunk = sf_id[i*5:(i+1)*5]
        val = 0
        for j, char in enumerate(chunk):
            if char.isupper():
                val += (1 << j) # Equivale a 2^j
        suffix += chars[val]
        
    return sf_id + suffix
