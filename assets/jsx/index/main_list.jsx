var React = require('react');
var ReactDOM = require('react-dom');

// Filters for api response. TODO: need to separate file.
var truncate = function(str,num){
  var words = str.split(' ');
  words = words.splice(0,num);
  return words.join(' ');
};

var orderBy = function(arr, len) {
  var chunks = [],
      i = 0,
      n = arr.length;
  while (i < n) {
    chunks.push(arr.slice(i, i += len));
  }
  return chunks;
};

var PostItem = React.createClass({
    render: function () {
        var groupNodes = this.props.group.map(function (post, i) {
            return <div className="col-xs-12 col-md-6" key={ i }>
                <div className="item_in_list">
                    <img src={post.photo.url} alt={ post.photo.description } id="image-list-size" className="img-rounded" />
                    <a href={ post.url }><h1 className="text-center">{ post.title }</h1></a>
                    <div className="text-justify" dangerouslySetInnerHTML={{__html: truncate(post.text, 40) }} />
                </div>
            </div>
            });
        return (
            <div>
                {groupNodes}
            </div>
        )
    }
});

var PostList = React.createClass({


    getInitialState: function() {
        return {data: []};
    },

    componentDidMount: function() {
        $.ajax({
            url: this.props.url,
            datatype: 'json',
            cache: false,
            success: function(data) {
                this.setState({data: orderBy(data.results, 2)});
            }.bind(this)
        })
    },
    render: function() {
        var postNodes = this.state.data.map(function (group, i) {
            return <div className="row" key={i}>
                      <PostItem group={group} />
                   </div>
        });
        return (
            <div id="items">
                {postNodes}
            </div>
        )
    }
});

ReactDOM.render(<PostList url='/api/post/all/' />, document.getElementById('main-list'));