document.addEventListener('DOMContentLoaded', () => {
    // Tab switching for index.html (Login / Register)
    const tabBtns = document.querySelectorAll('.auth-tab-btn');
    const authForms = document.querySelectorAll('.auth-form');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            authForms.forEach(f => f.classList.remove('active'));
            
            btn.classList.add('active');
            const targetForm = document.getElementById(`${targetTab}Form`);
            if (targetForm) targetForm.classList.add('active');
            clearErrors();
        });
    });

    // Helper: Clear invalid error highlights
    function clearErrors() {
        document.querySelectorAll('.form-control, .country-select').forEach(el => {
            el.classList.remove('is-invalid');
        });
        document.querySelectorAll('.error-text').forEach(el => {
            el.classList.remove('visible');
            el.textContent = '';
        });
    }

    // Clear error state on input change
    document.querySelectorAll('.form-control, .country-select').forEach(input => {
        input.addEventListener('input', () => {
            input.classList.remove('is-invalid');
            const errEl = input.parentElement.querySelector('.error-text');
            if (errEl) {
                errEl.classList.remove('visible');
            }
        });
    });

    // Auto-clean code inputs (strip spaces, dashes, letters)
    ['verifyCodeInput', 'mtprotoCodeInput'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', (e) => {
                e.target.value = e.target.value.replace(/\D/g, '');
            });
        }
    });

    // Helper: Set error on field (RED border)
    function setFieldError(fieldId, errorMsg) {
        const field = document.getElementById(fieldId);
        if (field) {
            field.classList.add('is-invalid');
            let errEl = field.parentElement.querySelector('.error-text');
            if (!errEl) {
                errEl = document.createElement('div');
                errEl.className = 'error-text';
                field.parentElement.appendChild(errEl);
            }
            errEl.textContent = errorMsg;
            errEl.classList.add('visible');
        }
    }

    // Login Form Handler
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            clearErrors();

            const formData = new FormData(loginForm);
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    if (result.requires_2fa) {
                        // Show 2FA Developer verification modal
                        document.getElementById('verifyPhoneHidden').value = result.phone_number;
                        const modal = document.getElementById('verifyModal');
                        if (modal) modal.classList.add('active');
                    } else {
                        window.location.href = result.redirect || '/dashboard';
                    }
                } else {
                    if (result.field) {
                        setFieldError(result.field, result.error);
                    } else {
                        setFieldError('loginPhone', result.error || 'Ошибка входа');
                    }
                }
            } catch (err) {
                setFieldError('loginPhone', 'Ошибка соединения с сервером');
            }
        });
    }

    // Registration Form Handler
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            clearErrors();

            const formData = new FormData(registerForm);
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    // Open Telegram Verification Modal
                    document.getElementById('verifyPhoneHidden').value = result.phone_number;
                    document.getElementById('verifyUsernameHidden').value = formData.get('username');
                    document.getElementById('verifyPasswordHidden').value = formData.get('password');
                    
                    const modal = document.getElementById('verifyModal');
                    if (modal) modal.classList.add('active');
                } else {
                    if (result.field) {
                        setFieldError(result.field, result.error);
                    } else {
                        setFieldError('regPhone', result.error || 'Ошибка регистрации');
                    }
                }
            } catch (err) {
                setFieldError('regPhone', 'Ошибка соединения с сервером');
            }
        });
    }

    // Verify Code Form Handler
    const verifyCodeForm = document.getElementById('verifyCodeForm');
    if (verifyCodeForm) {
        verifyCodeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const field = document.getElementById('verifyCodeInput');
            field.classList.remove('is-invalid');

            const formData = new FormData(verifyCodeForm);
            if (field) {
                formData.set('code', field.value.replace(/\D/g, ''));
            }
            try {
                const response = await fetch('/api/verify-code', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    window.location.href = result.redirect || '/dashboard';
                } else {
                    setFieldError('verifyCodeInput', result.error || 'Неверный код');
                }
            } catch (err) {
                setFieldError('verifyCodeInput', 'Ошибка соединения с сервером');
            }
        });
    }

    // Close Modal Handler
    const closeModalBtn = document.getElementById('closeModalBtn');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            const modal = document.getElementById('verifyModal');
            if (modal) modal.classList.remove('active');
        });
    }

    // Dashboard Tab Switching
    const dashMenuBtns = document.querySelectorAll('.dash-menu-btn');
    const dashTabContents = document.querySelectorAll('.dash-tab-content');

    dashMenuBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            dashMenuBtns.forEach(b => b.classList.remove('active'));
            dashTabContents.forEach(c => c.style.display = 'none');

            btn.classList.add('active');
            const targetContent = document.getElementById(`tab-${targetTab}`);
            if (targetContent) targetContent.style.display = 'block';
        });
    });

    // Dashboard: Update Device Limit Form Handler
    const deviceLimitForm = document.getElementById('deviceLimitForm');
    if (deviceLimitForm) {
        deviceLimitForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('limitUpdateMsg');
            msgEl.textContent = 'Обновление...';
            msgEl.style.color = 'var(--text-secondary)';

            const formData = new FormData(deviceLimitForm);
            try {
                const response = await fetch('/api/update-device-limit', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    msgEl.textContent = '✅ Лимит успешно обновлен!';
                    msgEl.style.color = 'var(--accent-green)';
                } else {
                    msgEl.textContent = result.error || 'Ошибка при обновлении';
                    msgEl.style.color = 'var(--accent-red)';
                }
            } catch (err) {
                msgEl.textContent = 'Ошибка соединения с сервером';
                msgEl.style.color = 'var(--accent-red)';
            }
        });
    }

    // MTProto: Send Code Handler
    window.onSendMtprotoCodeClick = async function(e) {
        if (e) e.preventDefault();
        const statusMsg = document.getElementById('mtprotoStatusMsg');
        if (statusMsg) {
            statusMsg.textContent = 'Отправка запроса в Telegram...';
            statusMsg.style.color = 'var(--text-secondary)';
        }

        try {
            const response = await fetch('/api/mtproto/send-code', { method: 'POST' });
            const result = await response.json();

            if (result.success) {
                if (statusMsg) {
                    statusMsg.textContent = '✅ Код успешно отправлен в ваше приложение Telegram!';
                    statusMsg.style.color = 'var(--accent-green)';
                }
                const modal = document.getElementById('mtprotoModal');
                if (modal) modal.classList.add('active');
            } else {
                if (statusMsg) {
                    statusMsg.textContent = '❌ Ошибка: ' + (result.error || 'Не удалось отправить код');
                    statusMsg.style.color = 'var(--accent-red)';
                }
                alert('Ошибка: ' + (result.error || 'Не удалось отправить код'));
            }
        } catch (err) {
            if (statusMsg) {
                statusMsg.textContent = 'Ошибка соединения с сервером';
                statusMsg.style.color = 'var(--accent-red)';
            }
            alert('Ошибка соединения с сервером');
        }
    };

    const sendMtprotoCodeBtn = document.getElementById('sendMtprotoCodeBtn');
    if (sendMtprotoCodeBtn) {
        sendMtprotoCodeBtn.addEventListener('click', window.onSendMtprotoCodeClick);
    }

    // MTProto: Verify Code Form Handler
    const mtprotoVerifyForm = document.getElementById('mtprotoVerifyForm');
    if (mtprotoVerifyForm) {
        mtprotoVerifyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(mtprotoVerifyForm);
            const codeInput = document.getElementById('mtprotoCodeInput');
            if (codeInput) {
                formData.set('code', codeInput.value.replace(/\D/g, ''));
            }

            try {
                const response = await fetch('/api/mtproto/verify-code', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    alert('🛡️ Авто-кик 3-го устройства успешно активирован!');
                    window.location.reload();
                } else {
                    if (result.requires_2fa) {
                        document.getElementById('2faContainer').style.display = 'block';
                        alert(result.error || 'Введите ваш облачный пароль (2FA) Telegram');
                    } else {
                        alert('Ошибка: ' + (result.error || 'Неверный код'));
                    }
                }
            } catch (err) {
                alert('Ошибка соединения с сервером');
            }
        });
    }

    const closeMtprotoModalBtn = document.getElementById('closeMtprotoModalBtn');
    if (closeMtprotoModalBtn) {
        closeMtprotoModalBtn.addEventListener('click', () => {
            const modal = document.getElementById('mtprotoModal');
            if (modal) modal.classList.remove('active');
        });
    }

    // Dashboard: Settings Form Handler
    const settingsForm = document.getElementById('settingsForm');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('settingsStatusMsg');
            msgEl.textContent = 'Сохранение...';
            msgEl.style.color = 'var(--text-secondary)';

            const formData = new FormData(settingsForm);
            try {
                const response = await fetch('/api/update-settings', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.success) {
                    msgEl.textContent = '✅ Настройки сохранены!';
                    msgEl.style.color = 'var(--accent-green)';
                } else {
                    msgEl.textContent = result.error || 'Ошибка при сохранении';
                    msgEl.style.color = 'var(--accent-red)';
                }
            } catch (err) {
                msgEl.textContent = 'Ошибка соединения с сервером';
                msgEl.style.color = 'var(--accent-red)';
            }
        });
    }

    // Dynamic 2FA OTP Functions
    window.loadCurrentOtp = async function() {
        try {
            const res = await fetch('/api/2fa/current-otp');
            const data = await res.json();
            const display = document.getElementById('otpCodeDisplay');
            if (display && data.has_otp && data.otp_password) {
                display.textContent = data.otp_password;
            }
        } catch (e) {}
    };

    window.copyOtpCode = function() {
        const display = document.getElementById('otpCodeDisplay');
        const btn = document.getElementById('copyOtpBtn');
        if (display && display.textContent) {
            const text = display.textContent.trim();
            if (text && text !== 'НЕ СГЕНЕРИРОВАН') {
                navigator.clipboard.writeText(text).then(() => {
                    if (btn) {
                        const orig = btn.textContent;
                        btn.textContent = '✅ Скопировано!';
                        setTimeout(() => { btn.textContent = orig; }, 2000);
                    }
                }).catch(() => {
                    alert('Код: ' + text);
                });
            }
        }
    };

    window.generateNewOtp = async function() {
        const display = document.getElementById('otpCodeDisplay');
        const msg = document.getElementById('otpMsg');
        const pwdInput = document.getElementById('otpCurrentPassword');
        const currentPassword = pwdInput ? pwdInput.value.trim() : '';

        if (msg) {
            msg.textContent = '⏳ Генерация и привязка к вашему Telegram...';
            msg.style.color = 'var(--text-secondary)';
        }

        const formData = new FormData();
        if (currentPassword) {
            formData.append('current_password', currentPassword);
        }

        try {
            const res = await fetch('/api/2fa/generate-otp', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (data.success) {
                if (display) display.textContent = data.otp_password;
                if (msg) {
                    msg.textContent = data.message || '✅ Облачный пароль успешно привязан!';
                    msg.style.color = 'var(--accent-green)';
                }
                if (pwdInput) pwdInput.value = '';
            } else {
                if (msg) {
                    msg.textContent = '❌ Ошибка: ' + (data.error || 'Не удалось привязать пароль');
                    msg.style.color = 'var(--accent-red)';
                }
            }
        } catch (e) {
            if (msg) {
                msg.textContent = 'Ошибка соединения с сервером';
                msg.style.color = 'var(--accent-red)';
            }
        }
    };

    // Auto-load OTP on page load if dashboard is open
    if (document.getElementById('otpCodeDisplay')) {
        window.loadCurrentOtp();
    }

    // Custom 2FA Password Form Handler
    const custom2faForm = document.getElementById('custom2faForm');
    if (custom2faForm) {
        custom2faForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msg = document.getElementById('custom2faMsg');
            if (msg) {
                msg.textContent = 'Обновление Облачного пароля в Telegram...';
                msg.style.color = 'var(--text-secondary)';
            }

            const formData = new FormData(custom2faForm);
            try {
                const res = await fetch('/api/2fa/update-custom-password', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (data.success) {
                    if (msg) {
                        msg.textContent = data.message || '✅ Облачный пароль успешно обновлен!';
                        msg.style.color = 'var(--accent-green)';
                    }
                } else {
                    if (msg) {
                        msg.textContent = '❌ Ошибка: ' + (data.error || 'Не удалось обновить пароль');
                        msg.style.color = 'var(--accent-red)';
                    }
                }
            } catch (e) {
                if (msg) {
                    msg.textContent = 'Ошибка соединения с сервером';
                    msg.style.color = 'var(--accent-red)';
                }
            }
        });
    }
});
