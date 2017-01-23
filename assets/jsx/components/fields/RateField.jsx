import React from 'react';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';

require('../../../scss/fields/rate_field.scss');

const RateField = React.createClass({
    mixins: [FieldErrorsMixin],

    render() {
        var errors = this.renderErrors(this.props.errors);
        return(
            <div className="form-group">
                <span className="help-block">{ errors }</span>
                <div className="star-rating__wrap">
                    <input key="5i"  className="star-rating__input" id="star-rating-5"
                           type="radio" name={this.props.name} value="5" />
                    <label key="5l" className="star-rating__ico fa fa-star-o fa-lg"
                           htmlFor="star-rating-5" title="це 5 з можливих 5" >  </label>
                    <input key="4i"  className="star-rating__input" id="star-rating-4"
                           type="radio" name={this.props.name} value="4" />
                    <label key="4l" className="star-rating__ico fa fa-star-o fa-lg"
                           htmlFor="star-rating-4" title="це 4 з можливих 5" >  </label>
                    <input key="3i"  className="star-rating__input" id="star-rating-3"
                           type="radio" name={this.props.name} value="3" />
                    <label key="3l" className="star-rating__ico fa fa-star-o fa-lg"
                           htmlFor="star-rating-3" title="це 3 з можливих 5" >  </label>
                    <input key="2i"  className="star-rating__input" id="star-rating-2"
                           type="radio" name={this.props.name} value="2" />
                    <label key="2l" className="star-rating__ico fa fa-star-o fa-lg"
                           htmlFor="star-rating-2" title="це 2 з можливих 5" >  </label>
                    <input key="1i"  className="star-rating__input" id="star-rating-1"
                           type="radio" name={this.props.name} value="1" />
                    <label key="1l" className="star-rating__ico fa fa-star-o fa-lg" 
                           htmlFor="star-rating-1" title="це 1 з можливих 5" >  </label>
                </div>
            </div>
        )
    }
});

export default RateField;