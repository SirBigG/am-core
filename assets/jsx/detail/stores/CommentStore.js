import DetailDispatcher from './../dispatcher/DetailDispatcher'
import events from 'events'
import CommentsConstants from './../constants/CommentsConstants'


var EventEmitter = events.EventEmitter;

var CHANGE_EVENT = 'change';

var _comments = [];

var CommentsStore = Object.assign({}, EventEmitter.prototype, {
    getComments() {
        return _comments;
    },
    setComments(comments) {
        Array.prototype.push.apply(_comments, comments)
    },
    setComment(comment){
        _comments.push(comment)
    },
    emitChange()  {
        this.emit(CHANGE_EVENT)
    },
    addChangeListener(cb) {
        this.on(CHANGE_EVENT, cb);
    },

    removeChangeListener(cb) {
        this.removeListener(CHANGE_EVENT, cb);
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
