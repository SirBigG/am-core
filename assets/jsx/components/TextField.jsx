import React from 'react';

// TODO: Creating help text and errors rendering if they are
// TODO: nice load with react now it ugly
const TextField = React.createClass({
    getInitialState() {
        return {value: ''}
    },
    componentDidMount(){
      CKEDITOR.replace(this.props.name, {language: 'uk', uiColor: '#9AB8F3'});
    },
    componentWillReceiveProps(newProps) {
        this.setState({value: newProps.value});
    },
    onChange(event) {
        this.setState({value: event.target.value})
    },
    render() {

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
            </div>
        )
    }
});

export default TextField;
