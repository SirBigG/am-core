import React from 'react';
import ReactDOM from 'react-dom';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';
var _ = require('lodash');

// TODO: create nice styles for component
// TODO: creating help text rendering
// TODO: scroll cursor up to top. Need to fix
// TODO: handler for form state changing because after save render previous value
var ulStyle = {
    overflow: 'hidden',
    overflowY: 'scroll'
};

var AutocompleteField = React.createClass({
    mixins: [FieldErrorsMixin],
    getInitialState() {
        return {data: [], next: "", value: "", scrollData: [], options: [], selectClass: ' hidden', defValue: ""};
    },
    componentWillReceiveProps(newProps) {
        this.setState({value: newProps.valueDefault.value, defValue:newProps.valueDefault.pk});
    },
    onChange(event) {
        this.setState({value: event.target.value});
        this.delayCallback()
    },
    onClick(value){
        this.setState({value: value, selectClass: ' hidden'});
    },
    onInputClick(e){
        e.preventDefault();
        this.setState({selectClass: ''})
    },
    onScroll(event){
        event.preventDefault();
        var el = ReactDOM.findDOMNode(this.refs.scrollDropdawn);
        if (el.offsetHeight + el.scrollTop - 2 === el.scrollHeight) {
            $.ajax({
                url: this.state.next,
                cache: false,
                success: function (data) {
                    this.setState({scrollData: data.results, next: data.next});
                    this.createOptions(this.state.scrollData)
                }.bind(this)
            });
            el.scrollTop = el.scrollHeight;
        }
    },
    componentWillMount() {
        $.ajax({
                url: this.props.url,
                cache: false,
                success: function (data) {
                    this.setState({data: data.results, next: data.next});
                    this.createOptions(this.state.data)
                }.bind(this)
        });
        this.delayCallback = _.debounce(() => {
            var url = this.props.url + '?loc=' + this.state.value;
            $.ajax({
                url: url,
                cache: false,
                success: function (data) {
                    this.setState({data: data.results, next: data.next});
                    this.state.options = [];
                    this.createOptions(this.state.data)
                }.bind(this)
            })}, 1000);
    },
    createOptions(data){
        return (data.map((item) => {
            return(
                this.state.options.push(
                    <option value={ item.pk } key={ item.pk } onClick={this.onClick.bind(this, item.value)}>
                        { item.value }
                    </option>
                )
            )}
            )
        )
    },
    render() {
        var errors = this.renderErrors(this.props.errors);
        return(
            <div className="form-group">
                <label>{this.props.label}</label>
                {errors}
                <input type="text" id="dropdown-input"
                       autoComplete="off"
                       data-toggle="dropdown"
                       aria-haspopup="true" 
                       aria-expanded="true"
                       onChange={this.onChange}
                       value={this.state.value}
                       className={this.props.class}
                       onClick={this.onInputClick}/>
                <select ref="scrollDropdawn"
                    name={this.props.name}
                    className={this.props.class + this.state.selectClass}
                    role="menu"
                    style={ulStyle}
                    size="5"
                    onScroll={this.onScroll}
                    value={this.state.defValue}>
                    {this.state.options}
                </select>
            </div>
        )
    }
});

export default AutocompleteField;
