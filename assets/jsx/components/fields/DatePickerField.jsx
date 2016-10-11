import React from 'react';
import ReactDOM from 'react-dom';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';
import 'bootstrap-datepicker/dist/js/bootstrap-datepicker';
import 'bootstrap-datepicker/dist/css/bootstrap-datepicker3.css';
import 'bootstrap-datepicker/js/locales/bootstrap-datepicker.uk';

// TODO: Creating help text and errors rendering if they are
const DatePickerField = React.createClass({
    mixins: [FieldErrorsMixin],
    componentDidMount: function(){
        var el = ReactDOM.findDOMNode(this.refs.datepicker);
        $(el).datepicker({format: "yyyy-mm-dd",
                          language: 'uk'});
    },
    componentWillReceiveProps(newProps){
        var el = ReactDOM.findDOMNode(this.refs.datepicker);
        $(el).datepicker('setDate', new Date(newProps.value))
    },
    render() {
        var errors = this.renderErrors(this.props.errors);
        return(
            <div className="form-group">
                <label>{this.props.label}</label>
                <input type='char'
                       value={this.props.value}
                       name={this.props.name}
                       onChange={this.props.onChange}
                       className={this.props.class}
                       ref="datepicker"
                       />
                { errors }
            </div>
        )
    }
});

export default DatePickerField;
