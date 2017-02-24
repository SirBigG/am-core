var $ = require('jquery');

// Rendering login form.
+function ($) {
    'use strict';
    $('body').on('click', '#login-btn', function () {
        $.ajax({
            type: 'GET',
            url:'/login/',
            success: function(res){$('#login-modal').html(res);}
        });
    })
}(jQuery);

// Login confirmation logic.
+function ($) {
    'use strict';
    $('body').on('click', '#login-conf-btn', function(){
            $.ajax({
            type: 'POST',
            url:'/login/',
            data: $('form').serialize(),
            success: function(res){
                // TODO: delete hard code from this block. Translation for button.
                // TODO: need profile button creating
                if(res.status === 'ok')
                {
                    var user_url = "location.href='/user/" + res.user + "/'";
                    $('#auth-btn').html(
                        '<li>' +
                        '<button onclick="' + user_url + '" ' +
                        'class="btn btn-primary navbar-btn"> Особистий кабінет </button> ' +
                        '<button onclick="location.href=/logout/" class="btn btn-primary navbar-btn"> Вийти </button>' +
                        '</li>'
                    );
                    $('.login-modal-lg').hide();
                    $('body').removeClass('modal-open');
                    $('.modal-backdrop').removeClass('modal-backdrop fade in');
                }
                else {
                    $('#login-modal').html(res);
                }
            },
            error: function(res){
                $('#login-modal').html(res);
            }
            });
            return false;
    });
}(jQuery);

// Rendering email confirm form.
+function ($) {
    'use strict';
    $('body').on('click', '#confirm-email-btn', function () {
        $.ajax({
            type: 'GET',
            url:'/password/confirm/email/',
            success: function(res){$('#login-modal').html(res);}
        });
        return false
    })
}(jQuery);

// Email confirmation logic.
+function ($) {
    'use strict';
    $('body').on('click', '#email-check-btn', function(){
            $.ajax({
            type: 'POST',
            url:'/password/confirm/email/',
            data: $('form').serialize(),
            success: function(res){
                if(res.status === 'ok')
                {

                    $('.login-modal-lg').hide();
                    $('body').removeClass('modal-open');
                    $(document).off('focusin.bs.modal');
                    $('.modal-backdrop').removeClass('modal-backdrop fade in');
                    alert('На пошту, що ви вказали відправлений лист підтвердження. ' +
                        'Перейдіть по посиланні в листі, щоб змінити свій пароль.' +
                        'Якщо лист не прийшов, обов’язково зв’яжіться з нами, використовуючи форму внизу сайту.');
                }
                else {
                    $('#login-modal').html(res);
                }
            },
            error: function(res){
                $('#login-modal').html(res);
            }
            });
            return false;
    });
}(jQuery);

// Password reset logic.
+function ($) {
    'use strict';
    $('body').on('click', '#password-change-btn', function(){
            $.ajax({
            type: 'POST',
            url: window.location.href,
            data: $('form').serialize(),
            success: function(res){
                    window.location = '/';
            },
            error: function(res){
                $('#check-password-form').html(res);
            }
            });
    });
}(jQuery);
