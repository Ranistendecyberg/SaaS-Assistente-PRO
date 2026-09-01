function extractTSI() {
    let results = [];
    // O Salesforce usa as classes even/odd para linhas de tabela
    let rows = document.querySelectorAll('tr.even, tr.odd');
    rows.forEach(row => {
        let cells = row.querySelectorAll('td');
        // Confirma se é a tabela correta baseada no número de colunas
        if (cells.length >= 7) {
            let idLink = cells[0].querySelector('a');
            if (!idLink) return; // Se não for link, pula
            
            let url = idLink.getAttribute('href');
            let sf_id = url.split('/').pop(); // Extrai o ID do final da URL
            let os_full = idLink.innerText.trim(); // Ex: 1014412-240966
            let os_formatado = os_full.includes('-') ? os_full.split('-')[1] : os_full;
            
            let chassi = cells[3].innerText.trim();
            let cliente = cells[4].innerText.trim();
            let email = cells[5].innerText.trim();
            let fone = cells[6].innerText.trim();
            
            // Tratamento do telefone: manter apenas números
            fone = fone.replace(/\D/g, ''); 
            
            results.push({
                tipo: 'TSI',
                id: sf_id,
                os: os_formatado,
                chassi: chassi,
                cliente: cliente,
                email: email,
                fone: fone
            });
        }
    });
    return results;
}
// Retorna a execução para o Python
extractTSI();
