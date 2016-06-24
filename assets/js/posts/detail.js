import 'bootstrap';
var $ = require('jquery');

// Rendering random posts on detail page.
+function ($) {
    'use strict';
    $(document).ready(
        $.ajax({
            type: 'GET',
            url:'/api/post/random/all/',
            success: function(response){
                var elements = $.map(response.results, function(post){
                     return '<div class="col-xs-6 col-md-3"><div class="item_in_list">' +
                            '<img src=' + post.photo.url + ' class="img-rounded" id="image-detail-list"/>' +
                            '<a href=' + post.url + '><h5 class="text-center">' + post.title + '</h5></a></div></div>' ;
                });
                $('#random-post-list').html(elements);
                }
            })
)}(jQuery);
