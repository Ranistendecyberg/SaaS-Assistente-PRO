"""Extração de campos rotulados da ficha, sem contatos no texto livre."""
CONTACT_EXTRACTOR_JS = r"""
(function () {
    const norm = s => (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLowerCase().replace(/\s+/g, ' ').trim().replace(/:$/, '').trim();
    const text = el => el ? (el.innerText || el.textContent || '').trim() : '';
    const result = {celular: '', modelo: '', email: '', record_id: '', error: ''};
    const id = location.pathname.match(/\/([a-zA-Z0-9]{18}|[a-zA-Z0-9]{15})(?:\/|$)/);
    result.record_id = id ? id[1] : '';
    const sections = [];
    for (const heading of document.querySelectorAll('.pbSubheader, h2, h3, h4')) {
        if (['dados para contato', 'tsi - informacoes do cliente'].includes(norm(text(heading)))) {
            const wrapper = heading.closest('.pbSubheader') || heading;
            if (wrapper.nextElementSibling) sections.push(wrapper.nextElementSibling);
        }
    }
    const emails = [], clientEmails = [], models = [], phones = [];
    for (const cell of document.querySelectorAll('td, th')) {
        const label = norm(text(cell)), value = text(cell.nextElementSibling);
        if (!value) continue;
        if (['e-mail do cliente', 'email do cliente'].includes(label)) clientEmails.push(value);
        else if (['email', 'e-mail'].includes(label) && sections.some(s => s.contains(cell))) emails.push(value);
        if (label === 'modelo') models.push(value);
        if (['celular', 'telefone', 'fone', 'telefone do cliente', 'celular do cliente',
             'telefone celular', 'telefone celular do cliente'].includes(label)) {
            const digits = value.replace(/\D/g, '').replace(/^0+/, '');
            if (digits.length >= 10 && digits.length <= 13) phones.push(digits);
        }
    }
    const unique = values => [...new Set(values)];
    const selectedEmails = unique(clientEmails.length ? clientEmails : emails);
    if (selectedEmails.length > 1) result.error = 'E-mails divergentes na ficha do cliente.';
    else result.email = selectedEmails[0] || '';
    const selectedModels = unique(models);
    if (selectedModels.length > 1) result.error = 'Modelos divergentes na ficha do cliente.';
    else result.modelo = selectedModels[0] || '';
    const selectedPhones = unique(phones);
    if (selectedPhones.length === 1) result.celular = selectedPhones[0];
    return result;
})();
"""
