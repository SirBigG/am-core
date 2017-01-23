import React from 'react';

var CommentItem = React.createClass({
    render(){
        var comment = this.props.comment;
        return <li className="media" id={comment.id}>
                <div className="media-body">
                    <div className="panel panel-default">
                        <div className="panel-body">
                    <h4 className="media-heading">{comment.user_sign}    <small>{comment.creation}</small></h4>
                    <p className="text-justify">{comment.text}</p>
                            </div>
                        </div>
                </div>
        </li>
    }
});


export default CommentItem;
