import React from 'react';

var CommentItem = React.createClass({
    render(){
        var comment = this.props.comment;
        return <div className={comment.level} id={comment.id}>
            <div className="clearfix bg-success comment-info">
                <div className="col-md-6">
                <strong>{comment.user_sign}</strong>
                    </div>
                <div className="col-md-6">
                    <p className="text-right">{comment.creation}</p>
                    </div>
            </div>
            <div className="clearfix comment-text">
                    <p>{comment.text}</p>
            </div>
        </div>
    }
});


export default CommentItem;
