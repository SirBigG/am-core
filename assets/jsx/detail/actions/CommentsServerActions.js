import DetailDispatcher from '../dispatcher/DetailDispatcher';
import CommentsConstants from '../constants/CommentsConstants';
import 'whatwg-fetch';

module.exports = {

    receiveComments: (url) => {
        fetch(url).then((response) => {
                    if (response.status === 200){
                            response.json().then((json) =>{
                                DetailDispatcher.handleServerAction({
                                    actionType: CommentsConstants.GET_COMMENTS_RESPONSE,
                                    data: json.results
                                });
                        });
                    }}
            );
    },
    createComment: (comment) => {
        DetailDispatcher.handleServerAction({
            actionType: CommentsConstants.CREATE_COMMENT,
            data: comment
        })
    }

};
