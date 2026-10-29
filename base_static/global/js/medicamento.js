// Cadastro de medicamento: autocompletar o nome com sugestões aproximadas
// (medicamentos já cadastrados + catálogo de produtos registrados no MAPA).
// O comportamento do autocompletar fica em app.js (criarAutocompletar)
document.addEventListener('DOMContentLoaded', () => {
    const campoNome = document.getElementById('nome-medicamento');
    const lista = document.getElementById('lista-sugestoes');
    if (!campoNome || !lista) return;

    const campoFabricante = document.getElementById('fabricante');
    const ajuda = document.getElementById('ajuda-nome-medicamento');
    const textoAjuda = ajuda.textContent.trim();

    // Desenho ilustrativo da forma (comprimido, injetável...): reutiliza os
    // símbolos SVG da página (sprite_formas.html)
    const SVG = 'http://www.w3.org/2000/svg';
    function criarIlustracao(forma, rotulo) {
        const quadro = document.createElement('span');
        quadro.className = `ilustracao ilustracao-pequena ilustracao-${forma}`;
        quadro.title = `Ilustração: ${rotulo}`;
        quadro.setAttribute('aria-hidden', 'true');
        const svg = document.createElementNS(SVG, 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        const uso = document.createElementNS(SVG, 'use');
        uso.setAttribute('href', `#forma-${forma}`);
        svg.append(uso);
        quadro.append(svg);
        return quadro;
    }

    // Conteúdo de cada sugestão (textContent: o texto nunca vira HTML)
    function montarItem(s) {
        const nome = document.createElement('div');
        nome.className = 'fw-semibold';
        nome.textContent = s.nome;
        const detalhe = document.createElement('div');
        detalhe.className = 'small text-body-secondary';
        const selos = document.createElement('div');
        selos.className = 'd-flex flex-wrap gap-1 mt-1';
        if (s.fonte === 'cadastrado') {
            detalhe.textContent = `Marcas já cadastradas: ${s.fabricante}`;
            selos.append(criarSelo('Já cadastrado', 'text-bg-secondary'));
        } else {
            detalhe.textContent = s.fabricante || 'Fabricante não informado';
            selos.append(criarSelo('Registrado no MAPA', 'selo-mapa'));
            if (s.natureza) selos.append(criarSelo(s.natureza, 'text-bg-light border'));
            if (s.licenca_provisoria) selos.append(criarSelo('Licença provisória', 'text-bg-warning'));
            if (s.animais_producao === true) selos.append(criarSelo('Animais de produção', 'text-bg-light border'));
        }
        // A forma também por escrito (o desenho é só visual)
        if (s.forma !== 'medicamento') selos.prepend(criarSelo(s.forma_rotulo, 'text-bg-light border'));
        // Desenho à esquerda, textos à direita
        const textos = document.createElement('div');
        textos.append(nome, detalhe, selos);
        const linha = document.createElement('div');
        linha.className = 'd-flex align-items-start gap-2';
        linha.append(criarIlustracao(s.forma, s.forma_rotulo), textos);
        return [linha];
    }

    function aoEscolher(s) {
        campoNome.value = s.nome;
        if (s.fonte === 'cadastrado') {
            // Esse nome já existe: o usuário informa outra marca
            campoFabricante.value = '';
            ajuda.textContent = `"${s.nome}" já está cadastrado (marcas: ${s.fabricante}). ` +
                'Informe outro fabricante para cadastrar uma nova marca.';
            campoFabricante.focus();
        } else {
            campoFabricante.value = s.fabricante;
            ajuda.textContent = 'Nome e fabricante preenchidos com os dados do registro no MAPA. Confira antes de cadastrar.';
            (s.fabricante ? campoFabricante.form.querySelector('button[type="submit"]') : campoFabricante).focus();
        }
    }

    criarAutocompletar({
        campo: campoNome,
        lista,
        url: campoNome.dataset.urlSugestoes,
        montarItem,
        aoEscolher,
        aoDigitar: () => { ajuda.textContent = textoAjuda; },
    });
});
