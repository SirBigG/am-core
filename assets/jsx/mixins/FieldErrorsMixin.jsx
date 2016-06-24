import  React from 'react';

const FieldErrorsMixin = {
    renderErrors(errors) {
        if(!errors)
        {
            return null;
        }

        return errors.map(this.renderError);
    },

    renderError(error, key) {
        if(!error || !error.length)
        {
            return null;
        }
        var error_key = 'error_'+key;
        return (
            <span key={error_key} className="text-danger">{ error }</span>
        );
    }

};

export default FieldErrorsMixin;
