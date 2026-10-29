// Formulário de estabelecimento: busca o endereço pelo CEP
document.addEventListener('DOMContentLoaded', () => {
    const campoCep = document.getElementById('cep');
    if (!campoCep) return;

    const botao = document.getElementById('btn-buscar-cep');
    const carregando = botao.querySelector('.spinner-border');
    const iconeBusca = botao.querySelector('.bi');
    const status = document.getElementById('status-cep');
    const campos = ['logradouro', 'bairro', 'cidade', 'uf'].reduce((mapa, id) => {
        mapa[id] = document.getElementById(id);
        return mapa;
    }, {});
    let ultimoCepBuscado = null;

    const somenteDigitos = (texto) => texto.replace(/\D/g, '').slice(0, 8);

    function mostrarStatus(texto, tipo) {
        status.textContent = texto;
        status.className = 'form-text' + (tipo ? ` text-${tipo}` : '');
    }

    function aguardando(sim) {
        botao.disabled = sim;
        carregando.hidden = !sim;
        iconeBusca.hidden = sim;
    }

    async function buscarCep() {
        const digitos = somenteDigitos(campoCep.value);
        if (digitos.length !== 8) {
            mostrarStatus('Digite os 8 números do CEP.', 'danger');
            return;
        }
        if (digitos === ultimoCepBuscado) return;
        ultimoCepBuscado = digitos;

        aguardando(true);
        mostrarStatus('Buscando endereço...');
        try {
            // Endpoint do próprio sistema (que consulta a ViaCEP/BrasilAPI)
            const url = campoCep.dataset.urlCep.replace('00000000', digitos);
            const resposta = await fetch(url, { headers: { Accept: 'application/json' } });
            const dados = await resposta.json();

            if (!resposta.ok) {
                mostrarStatus(dados.erro || 'Não foi possível buscar o CEP.', 'danger');
                ultimoCepBuscado = null;  // permite tentar de novo
                return;
            }

            // Preenche só o que a API trouxe (CEPs gerais de cidades pequenas
            // não têm rua nem bairro: nesse caso o usuário completa)
            Object.entries(campos).forEach(([id, campo]) => {
                if (dados[id]) campo.value = dados[id];
            });
            campoCep.value = dados.cep;
            mostrarStatus(`Endereço encontrado: ${dados.cidade}/${dados.uf}. Confira e informe o número.`, 'success');

            // Cursor no próximo campo que falta preencher
            const proximo = !dados.logradouro ? campos.logradouro
                : (!dados.bairro ? campos.bairro : document.getElementById('numero'));
            proximo.focus();
        } catch (erro) {
            mostrarStatus('Não foi possível buscar o CEP agora. Preencha o endereço manualmente.', 'danger');
            ultimoCepBuscado = null;
        } finally {
            aguardando(false);
        }
    }

    // Máscara 00000-000 enquanto digita; busca sozinho ao completar 8 números
    campoCep.addEventListener('input', () => {
        const digitos = somenteDigitos(campoCep.value);
        campoCep.value = digitos.length > 5 ? `${digitos.slice(0, 5)}-${digitos.slice(5)}` : digitos;
        if (digitos.length === 8) buscarCep();
    });
    campoCep.addEventListener('keydown', (evento) => {
        // Enter no CEP busca o endereço em vez de enviar o formulário
        if (evento.key === 'Enter') {
            evento.preventDefault();
            ultimoCepBuscado = null;
            buscarCep();
        }
    });
    botao.addEventListener('click', () => {
        ultimoCepBuscado = null;
        buscarCep();
    });
});

// Formulário de estabelecimento: CNPJ e busca por nome no MAPA
document.addEventListener('DOMContentLoaded', () => {
    const campoCnpj = document.getElementById('cnpj');
    if (!campoCnpj) return;

    const botao = document.getElementById('btn-buscar-cnpj');
    const carregando = botao.querySelector('.spinner-border');
    const iconeBusca = botao.querySelector('.bi');
    const status = document.getElementById('status-cnpj');
    const campoNome = document.getElementById('nome-farmacia');
    const CAMPOS = ['cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf'];
    let ultimoCnpj = null;

    const somenteDigitos = (texto) => texto.replace(/\D/g, '').slice(0, 14);
    const formatar = (d) => d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');

    function mostrarStatus(partes, tipo) {
        // Texto montado com textContent (dados externos nunca viram HTML)
        status.replaceChildren(...partes.map((p) => (typeof p === 'string' ? document.createTextNode(p) : p)));
        status.className = 'form-text' + (tipo ? ` text-${tipo}` : '');
    }

    function aguardando(sim) {
        botao.disabled = sim;
        carregando.hidden = !sim;
        iconeBusca.hidden = sim;
    }

    async function buscarCnpj(substituirNome) {
        const digitos = somenteDigitos(campoCnpj.value);
        if (digitos.length !== 14) {
            mostrarStatus(['Digite os 14 números do CNPJ.'], 'danger');
            return;
        }
        if (digitos === ultimoCnpj) return;
        ultimoCnpj = digitos;

        aguardando(true);
        mostrarStatus(['Buscando dados do CNPJ...']);
        try {
            let url = campoCnpj.dataset.urlCnpj.replace('00000000000000', digitos);
            if (campoCnpj.dataset.ignorar) url += `?ignorar=${campoCnpj.dataset.ignorar}`;
            const resposta = await fetch(url, { headers: { Accept: 'application/json' } });
            const dados = await resposta.json();
            if (!resposta.ok) {
                mostrarStatus([dados.erro || 'Não foi possível buscar o CNPJ.'], 'danger');
                ultimoCnpj = null;
                return;
            }

            campoCnpj.value = dados.cnpj_formatado;
            if (dados.nome && (substituirNome || !campoNome.value.trim())) campoNome.value = dados.nome;
            CAMPOS.forEach((id) => {
                const campo = document.getElementById(id);
                if (dados[id]) campo.value = dados[id];
            });
            if (dados.tipo_sugerido) {
                const opcao = document.getElementById(`tipo-${dados.tipo_sugerido}`);
                if (opcao) opcao.checked = true;
            }

            // Resumo do que foi encontrado
            const partes = [];
            let tipo = 'success';
            if (dados.ja_cadastrado) {
                partes.push('Atenção: este CNPJ já está cadastrado no sistema. ');
                tipo = 'danger';
            }
            if (dados.mapa && dados.mapa.ativo) {
                partes.push(criarSelo('Registrado no MAPA', 'selo-mapa'),
                    ` Nº ${dados.mapa.registro} (${dados.mapa.atividades.toLowerCase()}). `);
            } else if (dados.mapa) {
                partes.push(`Registro no MAPA ${dados.mapa.situacao.toLowerCase()}. `);
                if (tipo === 'success') tipo = 'warning';
            } else {
                partes.push('Sem registro no MAPA para produtos veterinários. ');
            }
            if (dados.situacao_receita && dados.situacao_receita !== 'ATIVA') {
                partes.push(`Situação na Receita: ${dados.situacao_receita}. `);
                if (tipo === 'success') tipo = 'warning';
            }
            partes.push(dados.endereco_completo ? 'Endereço preenchido: confira os dados.'
                : 'Complete o endereço (use o CEP).');
            mostrarStatus(partes, tipo);

            // Cursor no próximo campo que falta preencher
            const vazio = ['logradouro', 'numero', 'bairro', 'cidade'].map((id) => document.getElementById(id))
                .find((campo) => !campo.value.trim());
            (vazio || campoCnpj.form.querySelector('button[type="submit"]')).focus();
        } catch (erro) {
            mostrarStatus(['Não foi possível buscar o CNPJ agora. Preencha os dados manualmente.'], 'danger');
            ultimoCnpj = null;
        } finally {
            aguardando(false);
        }
    }

    // Máscara 00.000.000/0000-00; busca sozinho ao completar 14 números
    campoCnpj.addEventListener('input', () => {
        const d = somenteDigitos(campoCnpj.value);
        campoCnpj.value = d.length === 14 ? formatar(d) : d;
        if (d.length === 14) buscarCnpj(false);
    });
    campoCnpj.addEventListener('keydown', (evento) => {
        if (evento.key === 'Enter') {
            evento.preventDefault();
            ultimoCnpj = null;
            buscarCnpj(false);
        }
    });
    botao.addEventListener('click', () => {
        ultimoCnpj = null;
        buscarCnpj(false);
    });

    // Nome: sugestões de estabelecimentos registrados no MAPA
    const lista = document.getElementById('lista-estabelecimentos');
    if (!lista) return;

    criarAutocompletar({
        campo: campoNome,
        lista,
        url: campoNome.dataset.urlSugestoes,
        minimo: 3,
        montarItem(s) {
            const nome = document.createElement('div');
            nome.className = 'fw-semibold';
            nome.textContent = s.nome;
            const detalhe = document.createElement('div');
            detalhe.className = 'small text-body-secondary';
            detalhe.textContent = `${s.municipio}/${s.uf} · CNPJ ${s.cnpj_formatado}`;
            const selos = document.createElement('div');
            selos.className = 'd-flex flex-wrap gap-1 mt-1';
            selos.append(criarSelo('Registrado no MAPA', 'selo-mapa'));
            if (s.ja_cadastrado) selos.append(criarSelo('Já cadastrado', 'text-bg-secondary'));
            return [nome, detalhe, selos];
        },
        aoEscolher(s) {
            campoNome.value = s.nome;
            campoCnpj.value = s.cnpj_formatado;
            ultimoCnpj = null;
            buscarCnpj(true);
        },
    });
});
