document.addEventListener('DOMContentLoaded', () => {
    // Mapeamento dos elementos do DOM
    const modal = document.getElementById('auth-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const formLogin = document.getElementById('form-login');
    const formRegister = document.getElementById('form-register');
    
    // Botões da Seção Home (Landing Page)
    const btnHomeLogin = document.getElementById('btn-home-login');
    const btnHomeRegister = document.getElementById('btn-home-register');
    // Botão Sair no Menu
    const btnMenuLogin = document.getElementById('btn-menu-login');

    // Função para abrir o modal e definir a aba ativa
    function openAuthModal(targetTab) {
        modal.style.display = 'flex';
        switchTab(targetTab);
    }

    // Função para fechar o modal
    function closeAuthModal() {
        modal.style.display = 'none';
    }

    // Função para alternar as abas internas
    function switchTab(type) {
        if (type === 'login') {
            formLogin.style.display = 'block';
            formRegister.style.display = 'none';
            tabLogin.classList.add('active');
            tabRegister.classList.remove('active');
        } else {
            formLogin.style.display = 'none';
            formRegister.style.display = 'block';
            tabLogin.classList.remove('active');
            tabRegister.classList.add('active');
        }
    }

    // Ouvintes de Evento (Event Listeners) para os botões da Home
    if (btnHomeLogin) btnHomeLogin.addEventListener('click', () => openAuthModal('login'));
    if (btnHomeRegister) btnHomeRegister.addEventListener('click', () => openAuthModal('register'));
    if (btnMenuLogin) btnMenuLogin.addEventListener('click', (e) => {
        e.preventDefault(); // Evita que a página role ou saia do lugar pelo href="#"
        openAuthModal('login');
    });

    // Ouvintes de Evento interno do Modal
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeAuthModal);
    if (tabLogin) tabLogin.addEventListener('click', () => switchTab('login'));
    if (tabRegister) tabRegister.addEventListener('click', () => switchTab('register'));

    // Fecha o modal ao clicar fora (na área escura - overlay)
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeAuthModal();
        }
    });
});