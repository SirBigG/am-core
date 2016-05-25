
var $ = require('jquery');
require('bootstrap');
require('./auth/login');
require('./auth/register');
require('./services/feedback');

$(document).ready($('.carousel').carousel({interval: false}));
