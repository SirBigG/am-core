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
                        'class="btn btn-primary navbar-btn"> Особистий кабінет </button>' +
                        '<button onclick="location.href=/logout/" class="btn btn-primary navbar-btn"> Вийти </button>' +
                        '</li>'
                    );
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
