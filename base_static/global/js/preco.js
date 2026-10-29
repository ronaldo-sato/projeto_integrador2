// Página de preços: o campo Fabricante mostra apenas as marcas do
// medicamento escolhido, sem recarregar a página
document.addEventListener('DOMContentLoaded', () => {
    const formulario = document.getElementById('formulario-preco');
    if (!formulario) return;  // sem medicamentos/farmácias cadastrados

    // Lista de {id, nome, fabricante} enviada pelo servidor (json_script)
    const fabricantes = JSON.parse(document.getElementById('dados-fabricantes').textContent);
    const selectMedicamento = document.getElementById('select-medicamento');
    const selectFabricante = document.getElementById('select-fabricante');

    // Mesma comparação do servidor (nome__iexact): ignora maiúsculas
    const normalizar = (texto) => texto.trim().toLocaleLowerCase('pt-BR');

    function atualizarFabricantes(idSelecionado) {
        const nome = normalizar(selectMedicamento.value);
        const marcas = nome ? fabricantes.filter((m) => normalizar(m.nome) === nome) : [];

        // new Option() usa o texto como texto (nunca como HTML)
        selectFabricante.replaceChildren(
            new Option(nome ? 'Selecione o fabricante' : 'Escolha o medicamento', ''));
        marcas.forEach((m) => {
            const selecionado = String(m.id) === String(idSelecionado);
            selectFabricante.add(new Option(m.fabricante, m.id, selecionado, selecionado));
        });

        selectFabricante.disabled = marcas.length === 0;
        // Só existe uma marca: já deixa escolhida
        if (marcas.length === 1) selectFabricante.value = marcas[0].id;
    }

    // Ao abrir (inclusive após um erro), mantém o fabricante já escolhido
    atualizarFabricantes(selectFabricante.dataset.selecionado);
    selectMedicamento.addEventListener('change', () => {
        atualizarFabricantes('');
        if (!selectFabricante.disabled) selectFabricante.focus();
    });

    // Após um erro, coloca o cursor no campo que precisa ser corrigido
    const foco = formulario.dataset.foco;
    if (foco) {
        const campo = document.getElementById(foco);
        if (campo) campo.focus();
    }
});
