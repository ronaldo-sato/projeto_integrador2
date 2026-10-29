// Comportamentos da interface (usa o JavaScript do Bootstrap 5)

// ---------- Autocompletar (reutilizável) ----------
// Campo com sugestões buscadas no servidor enquanto o usuário digita.
// Acessível: setas navegam, Enter escolhe, Esc fecha; leitores de tela
// acompanham pelos atributos ARIA (combobox/listbox).
//   campo, lista: <input role="combobox"> e <ul role="listbox">
//   url: endereço que recebe ?q= e devolve {sugestoes: [...]}
//   montarItem(sugestao): nós (elementos) que formam o conteúdo de cada item
//   aoEscolher(sugestao) / aoDigitar(): o que fazer ao escolher / ao digitar
window.criarAutocompletar = function ({ campo, lista, url, minimo = 2, montarItem, aoEscolher, aoDigitar }) {
    const ESPERA_MS = 200;   // espera o usuário parar de digitar
    let sugestoes = [];
    let ativa = -1;
    let temporizador = null;
    let requisicao = null;   // permite cancelar a busca anterior

    function fechar() {
        lista.hidden = true;
        lista.replaceChildren();
        campo.setAttribute('aria-expanded', 'false');
        campo.removeAttribute('aria-activedescendant');
        ativa = -1;
    }

    function mostrar(itens) {
        sugestoes = itens;
        lista.replaceChildren();
        if (!itens.length) return fechar();
        itens.forEach((sugestao, indice) => {
            const item = document.createElement('li');
            item.className = 'list-group-item list-group-item-action';
            item.id = `${lista.id}-${indice}`;
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', 'false');
            item.append(...montarItem(sugestao));
            // mousedown (e não click) para escolher antes do campo perder o foco
            item.addEventListener('mousedown', (evento) => {
                evento.preventDefault();
                escolher(indice);
            });
            lista.append(item);
        });
        lista.hidden = false;
        campo.setAttribute('aria-expanded', 'true');
        ativa = -1;
    }

    function destacar(indice) {
        const itens = lista.querySelectorAll('[role="option"]');
        itens.forEach((item, i) => {
            item.classList.toggle('active', i === indice);
            item.setAttribute('aria-selected', String(i === indice));
        });
        ativa = indice;
        campo.setAttribute('aria-activedescendant', itens[indice].id);
        itens[indice].scrollIntoView({ block: 'nearest' });
    }

    function escolher(indice) {
        const sugestao = sugestoes[indice];
        fechar();
        if (sugestao) aoEscolher(sugestao);
    }

    async function buscar(texto) {
        if (requisicao) requisicao.abort();
        requisicao = new AbortController();
        try {
            const resposta = await fetch(`${url}?q=${encodeURIComponent(texto)}`, {
                headers: { Accept: 'application/json' }, signal: requisicao.signal });
            if (!resposta.ok) return fechar();
            const dados = await resposta.json();
            // Ignora respostas atrasadas (o usuário já digitou outra coisa)
            if (campo.value.trim() === texto) mostrar(dados.sugestoes);
        } catch (erro) {
            if (erro.name !== 'AbortError') fechar();
        }
    }

    campo.addEventListener('input', () => {
        if (aoDigitar) aoDigitar();
        clearTimeout(temporizador);
        const texto = campo.value.trim();
        if (texto.length < minimo) return fechar();
        temporizador = setTimeout(() => buscar(texto), ESPERA_MS);
    });

    campo.addEventListener('keydown', (evento) => {
        if (lista.hidden) return;
        const total = sugestoes.length;
        if (evento.key === 'ArrowDown') {
            evento.preventDefault();
            destacar((ativa + 1) % total);
        } else if (evento.key === 'ArrowUp') {
            evento.preventDefault();
            destacar((ativa - 1 + total) % total);
        } else if (evento.key === 'Enter' && ativa >= 0) {
            evento.preventDefault();
            escolher(ativa);
        } else if (evento.key === 'Escape') {
            fechar();
        }
    });

    campo.addEventListener('blur', () => setTimeout(fechar, 150));
};

// Selo (badge) com texto, criado sem HTML (o texto nunca vira código)
window.criarSelo = function (texto, classe) {
    const selo = document.createElement('span');
    selo.className = `badge rounded-pill ${classe}`;
    selo.textContent = texto;
    return selo;
};

document.addEventListener('DOMContentLoaded', () => {

    // ---------- Mensagens (toasts): somem sozinhas ----------
    // Sucesso some em 5 s; erros e avisos ficam 10 s para dar tempo de ler
    document.querySelectorAll('.mensagens .toast').forEach((elemento) => {
        const tempo = elemento.dataset.tipo === 'success' ? 5000 : 10000;
        bootstrap.Toast.getOrCreateInstance(elemento, { delay: tempo }).show();
    });

    // ---------- Janela de login / cadastro ----------
    const modalAuth = document.getElementById('auth-modal');
    if (modalAuth) {
        const janela = bootstrap.Modal.getOrCreateInstance(modalAuth);

        const abrirAba = (aba) => {
            const botaoAba = document.getElementById(aba === 'register' ? 'tab-register' : 'tab-login');
            bootstrap.Tab.getOrCreateInstance(botaoAba).show();
            janela.show();
        };

        // Botões "Entrar" / "Criar conta" (menu e página inicial)
        document.querySelectorAll('[data-abrir-autenticacao]').forEach((botao) => {
            botao.addEventListener('click', () => abrirAba(botao.dataset.abrirAutenticacao));
        });

        // Coloca o cursor no primeiro campo vazio da aba aberta
        modalAuth.addEventListener('shown.bs.modal', () => {
            const painel = modalAuth.querySelector('.tab-pane.active');
            const campo = [...painel.querySelectorAll('input:not([type=hidden])')].find((c) => !c.value)
                || painel.querySelector('input:not([type=hidden])');
            if (campo) campo.focus();
        });

        // Após um erro de login/cadastro (ou ao tentar abrir uma página que
        // exige login), a janela reabre na aba certa. O endereço volta para a
        // home para que atualizar a página (F5) não reenvie o formulário
        const abaAberta = modalAuth.dataset.abaAberta;
        if (abaAberta) {
            abrirAba(abaAberta);
            if (!window.location.search.includes('next=')) {
                history.replaceState(null, '', modalAuth.dataset.urlHome || '/');
            }
        }
    }

    // ---------- Mostrar / ocultar senha ----------
    // Botão com data-alternar-senha="#id-do-campo" troca o campo entre
    // senha (oculta) e texto (visível)
    document.querySelectorAll('[data-alternar-senha]').forEach((botao) => {
        const campo = document.querySelector(botao.dataset.alternarSenha);
        const icone = botao.querySelector('.bi');

        botao.addEventListener('click', () => {
            const mostrar = campo.type === 'password';
            campo.type = mostrar ? 'text' : 'password';
            icone.classList.toggle('bi-eye', !mostrar);
            icone.classList.toggle('bi-eye-slash', mostrar);
            const rotulo = mostrar ? 'Ocultar senha' : 'Mostrar senha';
            botao.setAttribute('aria-label', rotulo);
            botao.setAttribute('aria-pressed', String(mostrar));
            botao.title = rotulo;
            campo.focus();
        });
    });

    // Por segurança, a senha volta a ficar oculta ao enviar o formulário
    // ou ao fechar a janela
    const ocultarSenhas = () => document.querySelectorAll('[data-alternar-senha]').forEach((botao) => {
        const campo = document.querySelector(botao.dataset.alternarSenha);
        if (campo.type === 'text') botao.click();
    });
    document.querySelectorAll('#form-login, #form-register').forEach((f) => f.addEventListener('submit', ocultarSenhas));
    if (modalAuth) modalAuth.addEventListener('hidden.bs.modal', ocultarSenhas);

    // ---------- Confirmação antes de excluir ----------
    // Formulários com data-confirmar="mensagem" pedem confirmação antes de
    // enviar. A mensagem entra como texto (textContent), nunca como código
    const modalConfirmar = document.getElementById('modal-confirmar');
    if (modalConfirmar) {
        const janela = bootstrap.Modal.getOrCreateInstance(modalConfirmar);
        let formularioPendente = null;

        document.querySelectorAll('form[data-confirmar]').forEach((formulario) => {
            formulario.addEventListener('submit', (evento) => {
                if (formulario.dataset.confirmado) return;  // já confirmado
                evento.preventDefault();
                formularioPendente = formulario;
                document.getElementById('modal-confirmar-mensagem').textContent = formulario.dataset.confirmar;
                janela.show();
            });
        });

        document.getElementById('modal-confirmar-ok').addEventListener('click', () => {
            if (!formularioPendente) return;
            formularioPendente.dataset.confirmado = 'sim';
            formularioPendente.requestSubmit();
        });
    }

    // ---------- Filtro rápido das tabelas ----------
    // <input data-filtrar-tabela="#id-da-tabela"> esconde as linhas que não
    // contêm o texto digitado
    document.querySelectorAll('[data-filtrar-tabela]').forEach((campo) => {
        const tabela = document.querySelector(campo.dataset.filtrarTabela);
        const semResultado = document.querySelector(campo.dataset.semResultado);
        const normalizar = (texto) => texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

        campo.addEventListener('input', () => {
            const busca = normalizar(campo.value.trim());
            let visiveis = 0;
            tabela.querySelectorAll('tbody tr').forEach((linha) => {
                const mostrar = normalizar(linha.textContent).includes(busca);
                linha.hidden = !mostrar;
                if (mostrar) visiveis += 1;
            });
            if (semResultado) semResultado.hidden = visiveis > 0;
        });
    });
});
