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
                if(res === 'ok')
                {
                    $('#auth-btn').html('<li><a href="/logout/">' +
                    '<button class="btn btn-primary navbar-btn">Вийти</button>' +
                    '</a></li>');
                    $('.login-modal-lg').modal('hide');
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
