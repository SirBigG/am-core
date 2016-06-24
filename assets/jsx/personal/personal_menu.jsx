var React = require('react');

// Rendering user personal menu.
// Parameter is user id.
var PersonalMenu = React.createClass({
    render: function () {
        return (
            <ul class="nav nav-pills nav-stacked">
                <li role="presentation"><a href={'/user/${this.props.id}/'}>'Моя сторінка'</a></li>
                <li role="presentation"><a href={'/user/${this.props.id}/update/'}>'Змінити особисті дані'</a></li>
            </ul>
        )
    }
});