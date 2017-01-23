import events from 'events'

var EventEmitter = events.EventEmitter;

var CHANGE_EVENT = 'change';


var StoreEventsMixin = Object.assign ({}, EventEmitter.prototype, {
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

export default StoreEventsMixin;