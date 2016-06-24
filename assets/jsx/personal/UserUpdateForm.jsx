import React from 'react';
import ReactDOM from 'react-dom';
import AutocompleteField from '../components/AutocompleteField';
import InputField from '../components/InputField';
import ImageUploadField from '../components/ImageUploadField';
import DatePickerField from '../components/DatePickerField';
import GetCookieMixin from '../mixins/GetCookieMixin';
import FieldChangeHandlersMixin from '../mixins/FieldChangeHandlersMixin';


var UserUpdateForm = React.createClass({
    mixins: [GetCookieMixin, FieldChangeHandlersMixin],
    getInitialState() {
        return {data: [], errors: {}}
    },
    componentDidMount: function() {
        fetch("/users/" + this.props.params.user_id + "/",
            {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                        "X-CSRFToken": this.getCookie("csrftoken")
                }
            }
        )
            .then(
                (response) => {
                    if (response.status === 200){
                        response.json().then((json) => {this.setState({data: json})})
                    }
            }
            );
    },
    onSubmit(e){
        e.preventDefault();
        fetch("/users/" + this.props.params.user_id + "/",
            {
                method: 'PUT',
                credentials: 'same-origin',
                headers: {
                        "X-CSRFToken": this.getCookie("csrftoken")
                },
                body: new FormData(ReactDOM.findDOMNode(this.refs.form))
            }
        )
            .then(
                (response) => {
                    if(response.status === 400){
                        response.json().then((json) => {this.setState({errors: json})})
                    } else if (response.status === 200){
                        this.setState({errors: {}});
                        alert('Зміни успішно збережено');
                    }
                }
            )

    },
    render() {
        return(
            <form ref="form">
                <InputField type="email"
                            value={this.state.data.email}
                            name="email"
                            label="Email"
                            class="form-control"
                            errors={this.state.errors.email}
                            onChange={this.handleTextChange.bind(this, 'email')}/>
                <InputField type="char"
                            value={this.state.data.first_name}
                            name="first_name"
                            label="Ім’я"
                            class="form-control" 
                            errors={this.state.errors.first_name}
                            onChange={this.handleTextChange.bind(this, 'first_name')}/>
                <InputField type="char"
                            value={this.state.data.last_name}
                            name="last_name"
                            label="Прізвище"
                            class="form-control" 
                            errors={this.state.errors.last_name}
                            onChange={this.handleTextChange.bind(this, 'last_name')}/>
                <DatePickerField value={this.state.data.birth_date}
                                 name="birth_date"
                                 label="Дата народження"
                                 class="form-control"
                                 errors={this.state.errors.birth_date}
                                 onChange={this.handleTextChange.bind(this, 'birth_date')}/>
                <InputField type="char"
                            value={this.state.data.phone1}
                            name="phone1"
                            label="Телефон"
                            class="form-control"
                            errors={this.state.errors.phone1}
                            onChange={this.handleTextChange.bind(this, 'phone1')}/>
                <InputField type="char"
                            value={this.state.data.phone2}
                            name="phone2"
                            label="Інший телефон"
                            class="form-control" 
                            errors={this.state.errors.phone2} 
                            onChange={this.handleTextChange.bind(this, 'phone2')}/>
                <AutocompleteField url="/api/locations/" 
                                   value={this.state.data.location} 
                                   name="location" 
                                   label="Місце" 
                                   class="form-control"
                                   errors={this.state.errors.location}/>
                <ImageUploadField name="avatar"
                                  image_url={this.state.data.avatar_url}
                                  errors={this.state.errors.avatar}
                                  width="200"
                                  height="200"
                                  onChange={this.handleImageChange.bind(this, 'avatar_url')}/>
                    <button type="submit" className="btn btn-success btn-lg center-block" onClick={this.onSubmit}>Зберегти</button>
            </form>
        )
    }
});

export default UserUpdateForm;
