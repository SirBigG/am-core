import StoreEventsMixin from './../../mixins/StoreEventsMixin';
import 'whatwg-fetch';

var auth_data = new Map().set('is_auth', false).set('timestamp', 1000);

const timedelta = 60000;

var AuthStore = Object.assign({}, StoreEventsMixin, {
    getStatus() {
        if (this.isSend()){
           this.getResponse()
        }
        return auth_data.get('is_auth');
    },
    
    setStatus(_bool) {
        auth_data.set('is_auth', _bool);
    },
    
    isSend(){
        var now = new Date().getTime();
        if(auth_data.get('timestamp') && now - auth_data.get('timestamp') > timedelta){
            auth_data.set('timestamp', now);
            return true;
        } else {
            return false;
        }
    },
    
    getResponse(){
        fetch('/is-authenticate/', {
            method: 'get', headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin'}
            ).then((r) => {if (r.status === 200){r.json().then(
            (json) => {if (json.is_authenticate === 1){
                this.setStatus(true);
                this.emitChange();
            } else {
                this.setStatus(false);
                this.emitChange();  
            }
            })}});
    }
});

export default AuthStore;
