import React from 'react';
import ReactDOM from 'react-dom';
import 'whatwg-fetch';

import GetCookieMixin from '../../mixins/GetCookieMixin';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';

import {createComment} from './../actions/CommentsServerActions'

const fieldClass = "form-control";

var CommentsForm = React.createClass({
    mixins: [GetCookieMixin, FieldErrorsMixin],
    getInitialState() {
        return {errors: {}}
    },
    onSubmit(e){
        var postId = document.getElementById('comment').className;
        var formData = new FormData(ReactDOM.findDOMNode(this.refs.commentForm));
        formData.append('object_id', postId);
        fetch("/api/post/comments/",
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
                            createComment(json);
                            this._cleanForm()
                        })
                    }
                }
            );
        e.preventDefault();
    },

    _cleanForm() {
        ReactDOM.findDOMNode(this.refs.commentForm).reset();
        this.setState({errors: {}})
    },

    render() {
        var errors = this.renderErrors(this.state.errors.text);
        return(
            <form ref="commentForm">
                <div className="form-group">
                    <label>Ваш коментар</label>
                    <span className="help-block">{errors}</span>
                    <textarea  name="text"
                            className={fieldClass}
                            cols="5"
                            rows="5"/>
                </div>
                <div className="form-group">
                    <button type="submit" className="btn btn-success pull-right"
                            onClick={this.onSubmit}>Додати коментар</button>
                </div>
            </form>
        )
    }
});


export default CommentsForm;
