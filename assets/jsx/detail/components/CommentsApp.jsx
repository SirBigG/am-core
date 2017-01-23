import React from 'react';

import CommentsStore from '../stores/CommentStore';
import {receiveComments} from '../actions/CommentsServerActions'
import CommentItem from './CommentItem'
import CommentsForm from './CommentsForm'
import AuthStore from '../stores/AuthStore'


var CommentsApp = React.createClass({
    getInitialState() {
        return {comments: CommentsStore.getComments(), is_auth: AuthStore.getStatus() }
    },

    componentDidMount() {
        CommentsStore.addChangeListener(this._onChange);
        AuthStore.addChangeListener(this._authChange);
        receiveComments('/api/post/comments/?post=' + document.getElementById('comment').className)
    },

    componentWillUnmount() {
      CommentsStore.removeChangeListener(this._onChange);
      AuthStore.removeChangeListener(this._authChange);
    },
    
    _onChange() {
        this.setState({comments: CommentsStore.getComments()})
    },

    _authChange(){
        this.setState({is_auth: AuthStore.getStatus()})
    },
    
    render(){
        var commentNodes = this.state.comments.map((comment, i) => {
            return(<div key={i}><CommentItem comment={comment} /></div>)
        });
        var commentForm;
        if (this.state.is_auth){
            commentForm = <CommentsForm />;
        } else {
            commentForm = <div className="h4 text-center">
                <button id="login-btn" type="button" href="#" className="btn btn-link" data-toggle="modal" data-target=".login-modal-lg"><span className="h4">Увійдіть</span></button>щоб залишити коментар!</div>
        }
        return(
            <div id="comments">
                <ul className="media-list">
                    <li className="media"><div className="h4 clearfix">Коментарі:</div></li>
                    {commentNodes}
                </ul>
                <div className="comment-form clearfix">
                    {commentForm}
                </div>
            </div>
        )
    }
});

export default CommentsApp;