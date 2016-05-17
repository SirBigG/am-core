
$(document).ready(function feedback_get() {
    $.ajax({
        type: 'GET',
        url:'/service/feedback/',
        success: function(a){$('#feedback-modal').html(a);}
    });
});