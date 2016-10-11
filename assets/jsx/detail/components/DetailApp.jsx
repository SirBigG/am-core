import React from 'react';
import ReactDOM from 'react-dom';

import CommentsStore from '../stores/CommentStore';
import {receiveComments} from '../actions/CommentsServerActions'
import CommentItem from './CommentItem'
import CommentsForm from './CommentsForm'


var CommentsApp = React.createClass({
    getInitialState() {
        return {comments: [], is_authenticate: 0 }
    },

    receiveComments(){
        var commentEl = document.getElementById('comment');
        fetch('/api/post/comments/?post=' + commentEl.className).then((response) => {
                    if (response.status === 200){
                            response.json().then((json) =>{
                            receiveComments(json.results)
                        });
                    }}
            );
    },
    isAuthenticate(){
        // TODO: change this staff
        fetch('/is-authenticate/',
            {method: 'get', headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin'}
        ).then((r) => {if (r.status === 200){
                          r.json().then((json) => {this.setState({is_authenticate: json.is_authenticate})})
                       }
        });
    },
    
    componentDidMount() {
        CommentsStore.addChangeListener(this._onChange);
        this.isAuthenticate();
        this.receiveComments()
    },

    componentWillUnmount() {
      CommentsStore.removeChangeListener(this._onChange);
    },
    
    _onChange() {
        this.setState({comments: CommentsStore.getComments()})
    },
    
    render(){
        var commentNodes = this.state.comments.map((comment, i) => {
            return(<div key={i}><CommentItem comment={comment} /></div>)
        });
        var commentForm;
        if (this.state.is_authenticate === 1){
            commentForm = <CommentsForm />;
        } else {
            commentForm = <div className="h4 text-center">Ви не увійшли в систему <a href="/login/">Увійдіть</a> або <a href="/register/">Зареєструйтесь</a> щоб залишити коментар!</div>
        }
        return(
            <div id="comments">
                <div className="h4 clearfix">Коментарі:</div>
                {commentNodes}
                <div className="comment-form clearfix">
                    {commentForm}
                </div>
            </div>
        )
    }
});


ReactDOM.render(<CommentsApp />, document.getElementById('comment'));
