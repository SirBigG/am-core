import React from 'react';
import ReactDOM from 'react-dom';
import GetCookieMixin from '../../mixins/GetCookieMixin';
import FieldChangeHandlersMixin from '../../mixins/FieldChangeHandlersMixin';
import InputField from '../fields/InputField';
import TextField from '../fields/TextField';
import SelectField from '../fields/SelectField';
import PhotoSet from '../PhotoSet';
import 'whatwg-fetch';

const fieldClass = "form-control";

var UserPostForm = React.createClass({
    mixins: [GetCookieMixin, FieldChangeHandlersMixin],
    getInitialState() {
        return {data: [], errors: {}}
    },
    onSubmit(e){
        e.preventDefault();
        var formData = new FormData(ReactDOM.findDOMNode(this.refs.postForm));
        var nums = [1,2,3,4];
        var value = CKEDITOR.instances['text'].getData();
        formData.append('text', value);
        nums.map((i) => {
            if (formData.get('image'+i)) {
                formData.append('photos', formData.get('image' + i))
            }
            formData.delete('image'+i)
        });
        fetch("/api/user/posts/",
            {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                        "X-CSRFToken": this.getCookie("csrftoken")
                },
                body: formData
            }
        )
            .then(
                (response) => {
                    if(response.status === 400){
                        response.json().then((json) => {this.setState({errors: json})})
                    } else if (response.status === 201){
                        response.json().then((json) => {
                            window.location.href = json.url
                        })
                    }
                }
            )

    },
    render() {
        return(
            <form ref="postForm">
                <InputField type="char"
                            name="title"
                            label="Заголовок"
                            class={fieldClass}
                            errors={this.state.errors.title}/>
                <TextField name="text"
                           label="Текст"
                           class={fieldClass}
                           errors={this.state.errors.text}
                           cols="5"
                           rows="5"
                           height="450"/>
                <SelectField name="rubric"
                             label="Категорія"
                             class={fieldClass}
                             errors={this.state.errors.rubric}
                             url="/api/categories/?level=1"/>
                <PhotoSet errors={this.state.errors.photos}/>
                <InputField type="char"
                            name="Джерело"
                            label="Заголовок"
                            class={fieldClass}
                            errors={this.state.errors.source}/>
                <button type="submit" className="btn btn-success btn-lg center-block" onClick={this.onSubmit}>Зберегти</button>
            </form>
        )
    }
});


export default UserPostForm;