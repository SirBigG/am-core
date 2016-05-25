var $ = require('jquery');

// For register form rendering in modal window.
+function ($) {
    'use strict';
    $('body').on('click', '#register-btn', function () {
        $.ajax({
            type: 'GET',
            url:'/register/',
            success: function(res){$('#register-modal').html(res);}
        });
    })
}(jQuery);

// Register confirmation logic.
+function ($) {
    'use strict';
    $('body').on('click', '#register-conf-btn', function(){
            $.ajax({
            type: 'POST',
            url:'/register/',
            data: $('form').serialize(),
            success: function(res){
                // TODO: delete hard code from this block. Translation for text.
                if(res === 'ok')
                {
                    $('#register-modal').html('<h3 class="text-justify text-success">Дякуємо за реєстрацію!!! ' +
                        'На пошут, що ви вказали відправлений лист підтвердження. ' +
                        'Якщо лист не прийшов, обов’язково зв’яжіться з нами, використовуючи форму внизу сайту.</h3>');
                    setTimeout(function(){$('.register-modal-lg').modal('hide')},10000);
                }
                else {
                    $('#register-modal').html(res);
                }
            },
            error: function(res){
                $('#register-modal').html(res);
            }
            });
            return false;
    });
}(jQuery);

// For using popover in register form
$(document).ready(function(){
    $('[data-toggle="tooltip"]').popover();
});
