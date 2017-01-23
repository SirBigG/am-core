import React from 'react';
import ReactDOM from 'react-dom';

import GetCookieMixin from '../../mixins/GetCookieMixin';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';
import RateField from '../../components/fields/RateField'

const fieldClass = "form-control";

var ReviewForm = React.createClass({
    mixins: [GetCookieMixin, FieldErrorsMixin],
    getInitialState() {
        return {errors: {}, is_reviewed: false}
    },
    onSubmit(e){
        var slug = document.getElementById('reviews').className;
        var formData = new FormData(ReactDOM.findDOMNode(this.refs.reviewForm));
        formData.append('slug', slug);
        fetch("/api/category/reviews/",
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
                        this.setState({is_reviewed: true})
                    }
                }
            );
        e.preventDefault();
    },
    componentWillReceiveProps(newProps) {
        this.setState({is_reviewed: newProps.is_reviewed});
    },

    _cleanForm() {
        ReactDOM.findDOMNode(this.refs.reviewForm).reset();
        this.setState({errors: {}})
    },

    render() {
        var errors = this.renderErrors(this.state.errors.description);
        if (this.state.is_reviewed) {
            return(
                <span className="h5 text-success">Дякуємо за Ваш відгук! Він допоможе іншим користувачам.</span>
            )
        } else {
            return(
            <form ref="reviewForm">
                <div className="form-group">
                    <label>Текст відгуку</label>
                    <p className=" text-info">Опишіть плюси та мінуси в полі нижче. Або просто опишіть ваш досвід.</p>
                    <span className="help-block">{errors}</span>
                    <textarea  name="description"
                            className={fieldClass}
                            cols="5"
                            rows="5"/>
                </div>
                <RateField name="mark" errors={this.state.errors.mark}/>
                <div className="form-group">
                    <button type="submit" className="btn btn-success pull-right"
                            onClick={this.onSubmit}>Додати відгук</button>
                </div>
            </form>
        )
        }
    }
});

export default ReviewForm;
