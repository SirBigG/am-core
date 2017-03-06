import React from 'react';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';

// TODO: nice error rendering now not work right
// TODO: nice load with react now it ugly
// TODO: adding locale switcher for element if multilanguage done
const TextField = React.createClass({
    mixins: [FieldErrorsMixin],
    getInitialState() {
        return {value: ''}
    },
    componentDidMount(){
      CKEDITOR.replace(this.props.name, {language: 'uk', uiColor: '#428BCA', height: this.props.height,
          toolbar: [['Cut', 'Copy', 'Paste', '-', 'Undo', 'Redo'],['Bold', 'Italic'], ['NumberedList', 'BulletedList']]});
    },
    componentWillReceiveProps(newProps) {
        this.setState({value: newProps.value});
    },
    onChange(event) {
        this.setState({value: event.target.value})
    },
    render() {
        var errors = this.renderErrors(this.props.errors);
        
        return(
            <div className="form-group">
                <label>{this.props.label}</label>
                <textarea value={this.state.value}
                          name={this.props.name}
                          id={this.props.name}
                          onChange={this.onChange}
                          className={this.props.class}
                          cols={this.props.cols}
                          rows={this.props.rows}
                          />
                { errors }
            </div>
        )
    }
});

export default TextField;
