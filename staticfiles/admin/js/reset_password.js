window.addEventListener('DOMContentLoaded', function() {
    var newPass = document.querySelector('[name="new_password"]');
    var confirmPass = document.querySelector('[name="confirm_password"]');
    if (!newPass || !confirmPass) return;
    var newPassRow = newPass.closest('.form-row') || newPass.parentElement;
    var confirmPassRow = confirmPass.closest('.form-row') || confirmPass.parentElement;
    newPassRow.style.display = 'none';
    confirmPassRow.style.display = 'none';

    var passwordLabel = document.querySelector('label[for="id_password"]');
    if (passwordLabel) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.innerText = 'Reset Password';
        btn.style.marginLeft = '10px';
        btn.onclick = function() {
            newPassRow.style.display = '';
            confirmPassRow.style.display = '';
            newPass.focus();
        };
        passwordLabel.parentNode.appendChild(btn);
    }
}); 