import React from 'react';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';
import 'whatwg-fetch';

const SelectField = React.createClass({
    mixins: [FieldErrorsMixin],
    getInitialState() {
        return {data: []}
    },
    componentDidMount: function() {
        fetch(this.props.url, {method: 'GET'})
            .then(
                (response) => {
                    if (response.status === 200){
                        response.json().then((json) => {this.setState({data: json})})
                    }
            }
            );
    },
    render() {
        var options = this.state.data.map((item) => {
            return <option value={ item.pk } key={ item.pk }>
                        { item.value }
                    </option>
        });
        var errors = this.renderErrors(this.props.errors);
        
        return(
            <div className="form-group">
                <label>{this.props.label}</label>
                <select
                    name={this.props.name}
                    className={this.props.class}
                    role="menu">
                    <option value="">------------</option>
                    {options}
                </select>
                { errors }
            </div>
        )
    }
});


export default SelectField;
