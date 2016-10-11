import DetailDispatcher from '../dispatcher/DetailDispatcher';
import CommentsConstants from '../constants/CommentsConstants';


module.exports = {

    receiveComments: (data) => {
        DetailDispatcher.handleServerAction({
            actionType: CommentsConstants.GET_COMMENTS_RESPONSE,
            data: data
        })
    },
    createComment: (comment) => {
        DetailDispatcher.handleServerAction({
            actionType: CommentsConstants.CREATE_COMMENT,
            data: comment
        })
    }

};
