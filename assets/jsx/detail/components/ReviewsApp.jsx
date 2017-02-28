import React from 'react';
import 'whatwg-fetch';

import AuthStore from '../stores/AuthStore'
import ReviewForm from '../components/ReviewForm'


var ReviewsApp = React.createClass({
    getInitialState() {
        return {is_auth: undefined, is_reviewed: undefined, is_valid: undefined}
    },

    componentDidMount() {
        AuthStore.addChangeListener(this.authChange);
        this.authChange();
        this.isReviewed()
    },

    componentWillUnmount() {
      AuthStore.removeChangeListener(this.authChange);
    },

    isReviewed(){
        fetch('/service/reviews/is-reviewed/?slug=' + document.getElementById('reviews').className, {
            method: 'get', headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin'
        }
        ).then((r) => {
            if (r.status === 200) {
                r.json().then(
                    (json) => {
                        this.setState({is_reviewed: json['is-reviewed'] === 1,
                            is_valid: json['is-valid'] === 1});
                    })
            }
        });
    },

    authChange(){
        this.setState({is_auth: AuthStore.getStatus()})
    },

    render(){
        if (!this.state.is_valid){return (<div></div>)}
        var reviewForm = undefined;
        if (this.state.is_auth){
            reviewForm = this.state.is_reviewed ? <p className="text-info">Ви вже голосували!</p> :
                     <ReviewForm is_reviewed={this.state.is_reviewed} />
        } else {
            reviewForm = <div className="h4 text-center">
                <button id="login-btn" type="button" href="#" className="btn btn-link" data-toggle="modal" data-target=".login-modal-lg"><span className="h4">Увійдіть</span></button>щоб залишити відгук! Ваша оцінка допоможе іншим!</div>
        }
        // TODO: creating average reviews
        return(
            <div id="review__app">
                <p class="h4 text-success">Залишити відгук:</p>
                <div className="review-info"></div>
                <div className="review-form">
                    {reviewForm}
                </div>
            </div>
        )
    }
});

export default ReviewsApp;