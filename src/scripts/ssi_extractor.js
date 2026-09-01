function extractSSI() {
    let results = [];
    let rows = document.querySelectorAll('tr.even, tr.odd');
    rows.forEach(row => {
        let cells = row.querySelectorAll('td');
        // A tabela SSI tem pelo menos 4 colunas visíveis nesse contexto
        if (cells.length >= 4) {
            let idLink = cells[0].querySelector('a');
            if (!idLink) return;
            
            let url = idLink.getAttribute('href');
            let sf_id = url.split('/').pop();
            let posse_full = idLink.innerText.trim(); // Ex: 14598231-9C2KC...
            let posse_formatado = posse_full.includes('-') ? posse_full.split('-')[0] : posse_full;
            
            let data = cells[1].innerText.trim();
            let cliente = cells[2].innerText.trim();
            let chassi = cells[3].innerText.trim();
            
            // No SSI a ficha principal não tem Email, Fone e Modelo. 
            // Salvaremos a url_ficha para o bot navegar depois caso necessário.
            results.push({
                tipo: 'SSI',
                id: sf_id,
                posse: posse_formatado,
                data: data,
                cliente: cliente,
                chassi: chassi,
                url_ficha: url 
            });
        }
    });
    return results;
}
extractSSI();
