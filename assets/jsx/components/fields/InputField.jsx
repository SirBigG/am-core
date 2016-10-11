import React from 'react';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';

// TODO: Creating help text and errors rendering if they are
const InputField = React.createClass({
    mixins: [FieldErrorsMixin],
    render() {
        var errors = this.renderErrors(this.props.errors);
        return(
            <div className="form-group">
                <label>{this.props.label}</label>
                <input type={this.props.type}
                       value={this.props.value}
                       name={this.props.name}
                       onChange={this.props.onChange}
                       className={this.props.class}
                       id={this.props.id}
                       />
                { errors }
            </div>
        )
    }
});

export default InputField;
