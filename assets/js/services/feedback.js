var $ = require('jquery');

// Rendering feedback form.
+function ($) {
    'use strict';
    $('body').on('click', '#feedback-btn', function () {
        $.ajax({
            type: 'GET',
            url:'/service/feedback/',
            success: function(a){$('#feedback-modal').html(a);}
        });
    })
}(jQuery);

// Confirmation feedback.
+function ($) {
    'use strict';
    $('body').on('click', '#feedback-conf-btn', function () {
        $.ajax({
            type: 'POST',
            url: '/service/feedback/',
            data: $('form').serialize(),
            success: function (res) {
                $('#feedback-modal').html(res);
            },
            error: function (res) {
                $('#feedback-modal').html(res);
            }
        });
        return false;
    });
}(jQuery);
