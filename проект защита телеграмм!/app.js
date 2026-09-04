// Global Tab Switching function accessible from HTML onclick
window.switchAuthTab = function(tabName) {
    const tabBtns = document.querySelectorAll('.auth-tab-btn');
    const authForms = document.querySelectorAll('.auth-form');

    tabBtns.forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    authForms.forEach(form => {
        if (form.id === `${tabName}Form`) {
            form.classList.add('active');
            form.style.display = 'block';
        } else {
            form.classList.remove('active');
            form.style.display = 'none';
        }
    });

    if (typeof window.clearAuthErrors === 'function') {
        window.clearAuthErrors();
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // Tab switching event listeners
    const tabBtns = document.querySelectorAll('.auth-tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            if (e) e.preventDefault();
            const targetTab = btn.dataset.tab;
            window.switchAuthTab(targetTab);
        });
    });

    // Helper: Clear invalid error highlights
    window.clearAuthErrors = function() {
        document.querySelectorAll('.form-control, .country-select').forEach(el => {
            el.classList.remove('is-invalid');
        });
        document.querySelectorAll('.error-text').forEach(el => {
            el.classList.remove('visible');
            el.textContent = '';
        });
        const loginAlert = document.getElementById('loginAlertMsg');
        if (loginAlert) {
            loginAlert.style.display = 'none';
            loginAlert.textContent = '';
        }
        const regAlert = document.getElementById('registerAlertMsg');
        if (regAlert) {
            regAlert.style.display = 'none';
            regAlert.textContent = '';
        }
    };

    function clearErrors() {
        window.clearAuthErrors();
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

    // Helper: Set error on field with automatic ID mapping
    function setFieldError(fieldId, errorMsg, formType = 'login') {
        let field = document.getElementById(fieldId);
        if (!field) {
            if (fieldId === 'phone_number') {
                field = document.getElementById(formType === 'login' ? 'loginPhone' : 'regPhone');
            } else if (fieldId === 'password') {
                field = document.getElementById(formType === 'login' ? 'loginPassword' : 'regPassword');
            } else if (fieldId === 'username') {
                field = document.getElementById('regUsername');
            } else if (fieldId === 'code') {
                field = document.getElementById('verifyCodeInput');
            }
        }
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

            const submitBtn = document.getElementById('loginSubmitBtn');
            const alertMsg = document.getElementById('loginAlertMsg');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '⏳ Вход в систему...';
            }

            const formData = new FormData(loginForm);
            const phoneInputVal = (document.getElementById('loginPhone')?.value || '').trim();
            if (/[a-zA-Z_@]/.test(phoneInputVal)) {
                formData.set('country_code', '');
            }

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.requires_verification) {
                    const phoneHid = document.getElementById('verifyPhoneHidden');
                    const userHid = document.getElementById('verifyUsernameHidden');
                    const passHid = document.getElementById('verifyPasswordHidden');
                    if (phoneHid) phoneHid.value = result.phone_number || '';
                    if (userHid) userHid.value = result.username || '';
                    if (passHid) passHid.value = '';

                    const titleEl = document.getElementById('verifyModalTitle');
                    if (titleEl) titleEl.textContent = 'Подтверждение входа в систему';
                    const descEl = document.getElementById('verifyModalDesc');
                    if (descEl) {
                        descEl.innerHTML = 'Для подтверждения входа откройте бот <strong>@Defense_telegram_lerman_bot</strong>, нажмите <strong>«📱 Поделиться контактом»</strong> и введите полученный 6-значный код:';
                    }
                    const modal = document.getElementById('verifyModal');
                    if (modal) {
                        modal.classList.add('active');
                        const inp = document.getElementById('verifyCodeInput');
                        if (inp) {
                            inp.value = '';
                            inp.focus();
                        }
                    }
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Войти в систему';
                    }
                    return;
                }

                if (result.success) {
                    if (submitBtn) submitBtn.textContent = '✅ Успешно!';
                    if (result.user_id) {
                        document.cookie = "user_id=" + result.user_id + "; path=/; max-age=" + (86400 * 7) + "; SameSite=Lax";
                    }
                    const targetUrl = result.redirect || (result.user_id ? ('/dashboard?uid=' + result.user_id) : '/dashboard');
                    window.location.href = targetUrl;
                } else {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Войти в систему';
                    }
                    if (alertMsg) {
                        alertMsg.innerHTML = '❌ ' + (result.error || 'Ошибка входа') + 
                            ' <a href="#" onclick="switchAuthTab(\'register\'); return false;" style="color: var(--accent-cyan); font-weight: 700; text-decoration: underline; margin-left: 6px;">Зарегистрироваться</a>';
                        alertMsg.style.display = 'block';
                    }
                    if (result.field) {
                        setFieldError(result.field, result.error, 'login');
                    } else {
                        setFieldError('loginPhone', result.error || 'Ошибка входа', 'login');
                    }
                }
            } catch (err) {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Войти в систему';
                }
                if (alertMsg) {
                    alertMsg.textContent = '❌ Ошибка соединения с сервером';
                    alertMsg.style.display = 'block';
                }
                setFieldError('loginPhone', 'Ошибка соединения с сервером', 'login');
            }
        });
    }

    // Registration Form Handler
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            clearErrors();

            const submitBtn = document.getElementById('registerSubmitBtn');
            const alertMsg = document.getElementById('registerAlertMsg');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '⏳ Регистрация...';
            }

            const formData = new FormData(registerForm);
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();

                if (result.requires_verification) {
                    const phoneHid = document.getElementById('verifyPhoneHidden');
                    const userHid = document.getElementById('verifyUsernameHidden');
                    const passHid = document.getElementById('verifyPasswordHidden');
                    if (phoneHid) phoneHid.value = result.phone_number || '';
                    if (userHid) userHid.value = result.username || '';
                    if (passHid) passHid.value = result.password || '';

                    const titleEl = document.getElementById('verifyModalTitle');
                    if (titleEl) titleEl.textContent = 'Подтверждение регистрации';
                    const descEl = document.getElementById('verifyModalDesc');
                    if (descEl) {
                        descEl.innerHTML = 'Для завершения регистрации откройте бот <strong>@Defense_telegram_lerman_bot</strong>, нажмите <strong>«📱 Поделиться контактом»</strong> и введите полученный 6-значный код:';
                    }
                    const modal = document.getElementById('verifyModal');
                    if (modal) {
                        modal.classList.add('active');
                        const inp = document.getElementById('verifyCodeInput');
                        if (inp) {
                            inp.value = '';
                            inp.focus();
                        }
                    }
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Зарегистрироваться';
                    }
                    return;
                }

                if (result.success) {
                    if (submitBtn) submitBtn.textContent = '✅ Зарегистрировано!';
                    if (result.user_id) {
                        document.cookie = "user_id=" + result.user_id + "; path=/; max-age=" + (86400 * 7) + "; SameSite=Lax";
                    }
                    const targetUrl = result.redirect || (result.user_id ? ('/dashboard?uid=' + result.user_id) : '/dashboard');
                    window.location.href = targetUrl;
                } else {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Зарегистрироваться';
                    }
                    if (alertMsg) {
                        alertMsg.textContent = '❌ ' + (result.error || 'Ошибка регистрации');
                        alertMsg.style.display = 'block';
                    }
                    if (result.field) {
                        setFieldError(result.field, result.error, 'register');
                    } else {
                        setFieldError('regPhone', result.error || 'Ошибка регистрации', 'register');
                    }
                }
            } catch (err) {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Зарегистрироваться';
                }
                if (alertMsg) {
                    alertMsg.textContent = '❌ Ошибка соединения с сервером';
                    alertMsg.style.display = 'block';
                }
                setFieldError('regPhone', 'Ошибка соединения с сервером', 'register');
            }
        });
    }

    // Open Verify Modal Button Handler
    const openVerifyModalBtn = document.getElementById('openVerifyModalBtn');
    if (openVerifyModalBtn) {
        openVerifyModalBtn.addEventListener('click', (e) => {
            if (e) e.preventDefault();
            const modal = document.getElementById('verifyModal');
            if (modal) {
                modal.classList.add('active');
                const inp = document.getElementById('verifyCodeInput');
                if (inp) {
                    inp.value = '';
                    inp.focus();
                }
            }
        });
    }

    // Verify Code Form Handler
    const verifyCodeForm = document.getElementById('verifyCodeForm');
    if (verifyCodeForm) {
        verifyCodeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const field = document.getElementById('verifyCodeInput');
            const alertEl = document.getElementById('verifyAlertMsg');
            const submitBtn = document.getElementById('verifySubmitBtn');

            field.classList.remove('is-invalid');
            if (alertEl) {
                alertEl.style.display = 'none';
                alertEl.textContent = '';
            }
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '⏳ Проверка кода...';
            }

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
                    if (submitBtn) submitBtn.textContent = '✅ Вход в систему...';
                    if (result.user_id) {
                        document.cookie = "user_id=" + result.user_id + "; path=/; max-age=" + (86400 * 7) + "; SameSite=Lax";
                    }
                    const targetUrl = result.redirect || (result.user_id ? ('/dashboard?uid=' + result.user_id) : '/dashboard');
                    window.location.href = targetUrl;
                } else {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Войти в систему';
                    }
                    if (alertEl) {
                        alertEl.textContent = '❌ ' + (result.error || 'Неверный код из бота');
                        alertEl.style.display = 'block';
                    }
                    setFieldError('verifyCodeInput', result.error || 'Неверный код');
                }
            } catch (err) {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Войти в систему';
                }
                if (alertEl) {
                    alertEl.textContent = '❌ Ошибка соединения с сервером';
                    alertEl.style.display = 'block';
                }
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
            const errEl = document.getElementById('mtprotoVerifyErrorMsg');
            const submitBtn = document.getElementById('mtprotoVerifySubmitBtn');
            if (errEl) {
                errEl.style.display = 'none';
                errEl.textContent = '';
            }
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '⏳ Проверка кода...';
            }

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
                    if (submitBtn) submitBtn.textContent = '✅ Подключено!';
                    alert('🛡️ Авто-кик 3-го устройства успешно активирован!');
                    window.location.reload();
                } else {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Активировать защиту';
                    }
                    if (result.requires_2fa) {
                        const container2fa = document.getElementById('2faContainer');
                        if (container2fa) container2fa.style.display = 'block';
                        const pwdInput = document.getElementById('mtproto2faInput');
                        if (pwdInput) pwdInput.focus();
                        if (errEl) {
                            errEl.textContent = '🔒 ' + (result.error || 'Требуется облачный пароль Telegram (2FA)');
                            errEl.style.display = 'block';
                        }
                    } else {
                        if (errEl) {
                            errEl.textContent = '❌ ' + (result.error || 'Неверный код из Telegram');
                            errEl.style.display = 'block';
                        } else {
                            alert('Ошибка: ' + (result.error || 'Неверный код'));
                        }
                    }
                }
            } catch (err) {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Активировать защиту';
                }
                if (errEl) {
                    errEl.textContent = '❌ Ошибка соединения с сервером. Попробуйте еще раз.';
                    errEl.style.display = 'block';
                } else {
                    alert('Ошибка соединения с сервером');
                }
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

    // 2-Step Email Verification Handlers
    const requestEmailCodeForm = document.getElementById('requestEmailCodeForm');
    const verifyEmailCodeForm = document.getElementById('verifyEmailCodeForm');
    const emailActionMsg = document.getElementById('emailActionMsg');
    const cancelEmailCodeBtn = document.getElementById('cancelEmailCodeBtn');
    const targetEmailLabel = document.getElementById('targetEmailLabel');

    if (requestEmailCodeForm) {
        requestEmailCodeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const emailInput = document.getElementById('emailInput');
            const targetEmail = emailInput ? emailInput.value.trim() : '';

            if (emailActionMsg) {
                emailActionMsg.textContent = '⏳ Отправка проверочного кода на ' + targetEmail + '...';
                emailActionMsg.style.color = 'var(--text-secondary)';
            }

            const formData = new FormData(requestEmailCodeForm);
            try {
                const res = await fetch('/api/user/request-email-code', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    if (emailActionMsg) {
                        emailActionMsg.textContent = data.message || '📩 Код отправлен на вашу почту!';
                        emailActionMsg.style.color = 'var(--accent-cyan)';
                    }
                    if (targetEmailLabel) targetEmailLabel.textContent = targetEmail;
                    if (verifyEmailCodeForm) {
                        verifyEmailCodeForm.style.display = 'block';
                        const codeInp = document.getElementById('emailCodeInput');
                        if (codeInp) { codeInp.value = ''; codeInp.focus(); }
                    }
                    requestEmailCodeForm.style.display = 'none';
                } else {
                    if (emailActionMsg) {
                        emailActionMsg.textContent = '❌ ' + (data.error || 'Ошибка отправки кода');
                        emailActionMsg.style.color = 'var(--accent-red)';
                    }
                }
            } catch (err) {
                if (emailActionMsg) {
                    emailActionMsg.textContent = 'Ошибка соединения с сервером';
                    emailActionMsg.style.color = 'var(--accent-red)';
                }
            }
        });
    }

    if (cancelEmailCodeBtn) {
        cancelEmailCodeBtn.addEventListener('click', () => {
            if (verifyEmailCodeForm) verifyEmailCodeForm.style.display = 'none';
            if (requestEmailCodeForm) requestEmailCodeForm.style.display = 'flex';
            if (emailActionMsg) emailActionMsg.textContent = '';
        });
    }

    if (verifyEmailCodeForm) {
        verifyEmailCodeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (emailActionMsg) {
                emailActionMsg.textContent = '⏳ Проверка кода...';
                emailActionMsg.style.color = 'var(--text-secondary)';
            }

            const formData = new FormData(verifyEmailCodeForm);
            try {
                const res = await fetch('/api/user/verify-email-code', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    if (emailActionMsg) {
                        emailActionMsg.textContent = data.message || '✅ Почта успешно подтверждена и привязана!';
                        emailActionMsg.style.color = 'var(--accent-green)';
                    }
                    setTimeout(() => { window.location.reload(); }, 1500);
                } else {
                    if (emailActionMsg) {
                        emailActionMsg.textContent = '❌ ' + (data.error || 'Неверный код');
                        emailActionMsg.style.color = 'var(--accent-red)';
                    }
                }
            } catch (err) {
                if (emailActionMsg) {
                    emailActionMsg.textContent = 'Ошибка соединения с сервером';
                    emailActionMsg.style.color = 'var(--accent-red)';
                }
            }
        });
    }

    // Change Web Cabinet Password Form Handler
    const changeWebPasswordForm = document.getElementById('changeWebPasswordForm');
    if (changeWebPasswordForm) {
        changeWebPasswordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('changeWebPwdMsg');
            if (msgEl) {
                msgEl.textContent = '⏳ Обновление пароля...';
                msgEl.style.color = 'var(--text-secondary)';
            }

            const formData = new FormData(changeWebPasswordForm);
            try {
                const res = await fetch('/api/user/change-password', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    if (msgEl) {
                        msgEl.textContent = data.message || '✅ Пароль успешно обновлен!';
                        msgEl.style.color = 'var(--accent-green)';
                    }
                    changeWebPasswordForm.reset();
                } else {
                    if (msgEl) {
                        msgEl.textContent = '❌ ' + (data.error || 'Ошибка обновления пароля');
                        msgEl.style.color = 'var(--accent-red)';
                    }
                }
            } catch (err) {
                if (msgEl) {
                    msgEl.textContent = 'Ошибка соединения с сервером';
                    msgEl.style.color = 'var(--accent-red)';
                }
            }
        });
    }

    // Developer Panel Search & Actions
    const devSearch = document.getElementById('devUserSearchInput');
    if (devSearch) {
        devSearch.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            document.querySelectorAll('.dev-user-row').forEach(row => {
                const text = (row.getAttribute('data-search') || '').toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        });
    }

    window.devResetUserPassword = async function(userId, username) {
        const newPwd = prompt(`Сброс пароля кабинета для ${username} (ID: ${userId}):\nВведите новый пароль (или оставьте пустым для автогенерации):`);
        if (newPwd === null) return;

        const statusEl = document.getElementById('devActionStatusMsg');
        if (statusEl) {
            statusEl.textContent = '⏳ Сброс пароля...';
            statusEl.style.color = 'var(--text-secondary)';
        }

        const formData = new FormData();
        formData.append('target_user_id', userId);
        if (newPwd.trim()) {
            formData.append('new_password', newPwd.trim());
        }

        try {
            const res = await fetch('/api/dev/reset-user-password', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success) {
                if (statusEl) {
                    statusEl.textContent = data.message;
                    statusEl.style.color = 'var(--accent-green)';
                }
                alert(data.message);
            } else {
                if (statusEl) {
                    statusEl.textContent = '❌ ' + (data.error || 'Ошибка');
                    statusEl.style.color = 'var(--accent-red)';
                }
            }
        } catch (e) {
            if (statusEl) {
                statusEl.textContent = 'Ошибка соединения с сервером';
                statusEl.style.color = 'var(--accent-red)';
            }
        }
    };

    window.devResetCloud2FA = async function(userId, username) {
        const new2fa = prompt(`Установка нового Облачного пароля Telegram (2FA) для ${username} (ID: ${userId}):\nВведите код (или оставьте пустым для генерации SHIELD-XXXXXX):`);
        if (new2fa === null) return;

        const statusEl = document.getElementById('devActionStatusMsg');
        if (statusEl) {
            statusEl.textContent = '⏳ Установка нового Облачного пароля в Telegram...';
            statusEl.style.color = 'var(--text-secondary)';
        }

        const formData = new FormData();
        formData.append('target_user_id', userId);
        if (new2fa.trim()) {
            formData.append('new_2fa_code', new2fa.trim());
        }

        try {
            const res = await fetch('/api/dev/reset-cloud-2fa', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success) {
                if (statusEl) {
                    statusEl.textContent = data.message;
                    statusEl.style.color = 'var(--accent-green)';
                }
                alert(data.message);
                setTimeout(() => { window.location.reload(); }, 1200);
            } else {
                if (statusEl) {
                    statusEl.textContent = '❌ ' + (data.error || 'Ошибка');
                    statusEl.style.color = 'var(--accent-red)';
                }
            }
        } catch (e) {
            if (statusEl) {
                statusEl.textContent = 'Ошибка соединения с сервером';
                statusEl.style.color = 'var(--accent-red)';
            }
        }
    };
});
