import DetailDispatcher from './../dispatcher/DetailDispatcher'
import CommentsConstants from './../constants/CommentsConstants'
import StoreEventsMixin from './../../mixins/StoreEventsMixin'

var _comments = [];

var CommentsStore = Object.assign({}, StoreEventsMixin, {
    getComments() {
        return _comments;
    },
    setComments(comments) {
        Array.prototype.push.apply(_comments, comments)
    },
    setComment(comment){
        _comments.push(comment)
    }
});


DetailDispatcher.register((payload) => {
    var action = payload.action;

    switch (action.actionType){
        case CommentsConstants.GET_COMMENTS_RESPONSE:
            CommentsStore.setComments(action.data);
            break;
        case CommentsConstants.CREATE_COMMENT:
            CommentsStore.setComment(action.data);
            break;
        default:
            return true;
    }
    CommentsStore.emitChange();
    return true
});

export default CommentsStore;
