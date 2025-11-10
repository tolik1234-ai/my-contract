(function () {
    document.addEventListener('DOMContentLoaded', () => {
        initWalletConnection();
        initScatterText();
        initScrollPanels();
    });

    function initWalletConnection() {
        const connectButton = document.querySelector('[data-connect-wallet]');
        const walletLabel = connectButton?.querySelector('[data-wallet-label]');
        const statusElement = document.querySelector('[data-wallet-status]');
        const messageElement = document.querySelector('[data-wallet-message]');
        const inlineStatusElements = document.querySelectorAll('[data-wallet-status-inline]');

        if (!connectButton || !statusElement) {
            return;
        }

        async function requestAccounts() {
            if (typeof window === 'undefined' || !window.ethereum) {
                if (messageElement) {
                    messageElement.textContent = 'No Ethereum provider detected. Install MetaMask or use WalletConnect.';
                }
                return;
            }

            try {
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                handleAccountsChanged(accounts);
            } catch (error) {
                if (error.code === 4001) {
                    if (messageElement) {
                        messageElement.textContent = 'Connection rejected. Try again when you are ready to sign.';
                    }
                } else {
                    if (messageElement) {
                        messageElement.textContent = 'Unable to connect to wallet. Check console for more details.';
                    }
                    console.error('Wallet connection error:', error);
                }
            }
        }

        function setDisconnectedState() {
            if (messageElement) {
                messageElement.textContent = 'No wallet connected yet. Use the button above to link a signer.';
            }
            connectButton.classList.remove('is-connected');
            connectButton.disabled = false;
            if (walletLabel) {
                walletLabel.textContent = 'Connect wallet';
            }
            inlineStatusElements.forEach((element) => {
                element.textContent = '0x0000…0000';
                if (element.hasAttribute('data-wallet-source')) {
                    delete element.dataset.fullAddress;
                }
            });
        }

        function handleAccountsChanged(accounts) {
            if (!accounts || accounts.length === 0) {
                setDisconnectedState();
                return;
            }

            const primaryAccount = accounts[0];
            if (messageElement) {
                messageElement.textContent = 'Wallet connected. Sign actions directly from this browser.';
            }
            connectButton.classList.add('is-connected');
            connectButton.disabled = true;
            if (walletLabel) {
                walletLabel.textContent = 'Wallet connected';
            }
            inlineStatusElements.forEach((element) => {
                element.textContent = formatAddress(primaryAccount);
                if (element.hasAttribute('data-wallet-source')) {
                    element.dataset.fullAddress = primaryAccount;
                }
            });
        }

        connectButton.addEventListener('click', requestAccounts);

        if (typeof window !== 'undefined' && window.ethereum) {
            window.ethereum
                .request({ method: 'eth_accounts' })
                .then((accounts) => {
                    if (!accounts || accounts.length === 0) {
                        setDisconnectedState();
                    } else {
                        handleAccountsChanged(accounts);
                    }
                })
                .catch((error) => console.error('Unable to read wallet accounts', error));

            window.ethereum.on?.('accountsChanged', handleAccountsChanged);
        } else {
            setDisconnectedState();
        }
    }

    function formatAddress(address) {
        if (!address || address.length < 10) {
            return address || '';
        }
        return `${address.slice(0, 6)}…${address.slice(-4)}`;
    }

    function initScatterText() {
        const scatterTargets = document.querySelectorAll('[data-scatter]');

        scatterTargets.forEach((element) => {
            const originalText = element.textContent || '';
            element.textContent = '';
            const characters = Array.from(originalText);

            characters.forEach((char, index) => {
                const span = document.createElement('span');
                span.textContent = char;
                if (char === ' ') {
                    span.classList.add('is-space');
                }
                span.style.setProperty('--delay', `${index * 12}ms`);
                element.appendChild(span);
            });

            element.classList.add('scatter-ready');

            element.addEventListener('mouseenter', () => scatter(element));
            element.addEventListener('focus', () => scatter(element));
            element.addEventListener('mouseleave', () => resetScatter(element));
            element.addEventListener('blur', () => resetScatter(element));
        });
    }

    function scatter(element) {
        element.classList.add('is-scattered');
        element.querySelectorAll('span').forEach((span) => {
            const tx = (Math.random() - 0.5) * 50;
            const ty = (Math.random() - 0.5) * 40;
            const rot = (Math.random() - 0.5) * 40;
            span.style.setProperty('--tx', `${tx.toFixed(2)}px`);
            span.style.setProperty('--ty', `${ty.toFixed(2)}px`);
            span.style.setProperty('--rot', `${rot.toFixed(2)}deg`);
        });
    }

    function resetScatter(element) {
        element.classList.remove('is-scattered');
        element.querySelectorAll('span').forEach((span) => {
            span.style.setProperty('--tx', '0px');
            span.style.setProperty('--ty', '0px');
            span.style.setProperty('--rot', '0deg');
        });
    }

    function initScrollPanels() {
        const panels = document.querySelectorAll('[data-scroll-container]');

        panels.forEach((panel) => {
            const track = panel.querySelector('[data-scroll-track]');
            const prevButton = panel.querySelector('[data-scroll-prev]');
            const nextButton = panel.querySelector('[data-scroll-next]');

            if (!track) {
                return;
            }

            const scrollAmount = () => track.clientWidth * 0.75;

            const updateButtons = () => {
                const maxScrollLeft = track.scrollWidth - track.clientWidth;
                if (prevButton) {
                    prevButton.disabled = track.scrollLeft <= 4;
                }
                if (nextButton) {
                    nextButton.disabled = track.scrollLeft >= maxScrollLeft - 4;
                }
            };

            prevButton?.addEventListener('click', () => {
                track.scrollBy({ left: -scrollAmount(), behavior: 'smooth' });
            });

            nextButton?.addEventListener('click', () => {
                track.scrollBy({ left: scrollAmount(), behavior: 'smooth' });
            });

            track.addEventListener('scroll', updateButtons, { passive: true });
            window.addEventListener('resize', updateButtons);
            updateButtons();
        });
    }
})();
