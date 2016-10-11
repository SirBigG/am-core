import React from 'react';
import FieldErrorsMixin from '../../mixins/FieldErrorsMixin';


const ImageUploadField = React.createClass ({
    
    mixins: [FieldErrorsMixin],
    
    getInitialState(){
        return { imagePreviewUrl: ''}
    },

  componentWillReceiveProps(newProps) {
      this.setState({imagePreviewUrl: newProps.image_url})
  },

  render() {
      let $imagePreview = null;
      if (this.state.imagePreviewUrl) {
          $imagePreview = (<img src={this.state.imagePreviewUrl} className="img-responsive" width={this.props.width}
          height={this.props.height}/>);
      } else {
          $imagePreview = (<div className="previewText">Будь-ласка виберіть зображення в полі вище</div>);
      }
      var errors = this.renderErrors(this.props.errors);
      return (
          <div className="form-group">
              <label className="btn btn-success">
                  <input type="file"
                         onChange={this.props.onChange}
                         className="hidden"
                         name={this.props.name} />
                  <i className="fa fa-plus-circle fo-3x" aria-hidden="true"> Додати фото</i>
              </label>
              {errors}
              <div className="imgPreview">
                  {$imagePreview}
              </div>
          </div>
      )
  }
});

export default ImageUploadField;
